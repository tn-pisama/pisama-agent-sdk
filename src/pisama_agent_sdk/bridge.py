"""Detection Bridge - connects Agent SDK hooks to MAO detection."""

import asyncio
import logging
import re
import time
from typing import Any, Optional

from pisama_core.detection.orchestrator import DetectionOrchestrator, RealtimeResult
from pisama_core.detection.registry import DetectorRegistry
from pisama_core.detection.registry import registry as global_registry

from .config import BridgeConfig
from .converter import HookInputConverter
from .session import SessionManager, session_manager
from .types import BridgeResult, HookInput

logger = logging.getLogger(__name__)


class DetectionBridge:
    """Bridge between Agent SDK hooks and MAO detection.

    This is the core integration layer that:
    1. Converts HookInput to Span format
    2. Maintains session context
    3. Runs real-time detection with timeout
    4. Generates appropriate hook outputs

    Example:
        bridge = DetectionBridge()

        # PreToolUse hook
        result = await bridge.analyze_pre_tool(hook_input, tool_use_id)
        if result.should_block:
            return {"permissionDecision": "block", ...}

        # PostToolUse hook
        result = await bridge.analyze_post_tool(hook_input, tool_use_id)
        if result.system_message:
            return {"systemMessage": result.system_message}
    """

    def __init__(
        self,
        config: Optional[BridgeConfig] = None,
        detector_registry: Optional[DetectorRegistry] = None,
        session_mgr: Optional[SessionManager] = None,
    ) -> None:
        """Initialize the detection bridge.

        Args:
            config: Bridge configuration (defaults to BridgeConfig())
            detector_registry: Detector registry (defaults to global)
            session_mgr: Session manager (defaults to global)
        """
        self.config = config or BridgeConfig()
        self.registry = detector_registry or global_registry
        self.sessions = session_mgr or session_manager

        self.converter = HookInputConverter()
        self.orchestrator = DetectionOrchestrator(
            registry=self.registry,
            severity_threshold=self.config.warning_threshold,
            block_threshold=self.config.block_threshold,
            parallel=True,
        )

        # Compile tool patterns
        self._include_patterns = [re.compile(p) for p in self.config.tool_patterns]
        self._exclude_patterns = [
            re.compile(f"^{re.escape(t)}$") for t in self.config.excluded_tools
        ]

    async def analyze_pre_tool(
        self,
        hook_input: HookInput,
        tool_use_id: Optional[str] = None,
    ) -> BridgeResult:
        """Analyze tool call before execution (PreToolUse).

        This runs detection with strict timeout to decide whether
        to block the tool call.

        Args:
            hook_input: Input data from Agent SDK
            tool_use_id: Unique tool invocation ID

        Returns:
            BridgeResult with blocking decision and messages
        """
        start_time = time.perf_counter()
        tool_name = hook_input.get("tool_name", "")

        # Check if tool should be analyzed
        if not self._should_analyze(tool_name):
            return BridgeResult(execution_time_ms=0)

        session_id = hook_input.get("session_id", "unknown")

        # Check if session is already blocked
        if self.sessions.is_blocked(session_id):
            return BridgeResult(
                should_block=True,
                severity=100,
                issues=["Session is blocked due to previous violations"],
                block_reason=self.sessions.get_block_reason(session_id),
                system_message=self._format_blocked_message(session_id),
            )

        # Convert to span
        span = self.converter.to_span(hook_input, tool_use_id, is_post=False)

        # Get session context
        context = self.sessions.get_context(
            session_id, window=self.config.context_window
        )

        # Run detection with timeout
        try:
            result = await asyncio.wait_for(
                self.orchestrator.analyze_realtime(span, context),
                timeout=self.config.detection_timeout_ms / 1000,
            )
            timed_out = False
        except asyncio.TimeoutError:
            logger.warning(
                f"Detection timeout for tool {tool_name} "
                f"(>{self.config.detection_timeout_ms}ms)"
            )
            # Timeout: allow to proceed but log
            return BridgeResult(
                timed_out=True,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Add span to session (after analysis)
        self.sessions.add_span(session_id, span)

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Build result
        should_block = (
            self.config.enable_blocking
            and result.should_block
            and result.severity >= self.config.block_threshold
        )

        bridge_result = BridgeResult(
            should_block=should_block,
            severity=result.severity,
            issues=result.issues,
            recommendations=self._extract_recommendations(result),
            block_reason=result.block_reason,
            execution_time_ms=execution_time_ms,
            timed_out=timed_out,
        )

        # Generate system message for warnings or blocks
        if result.severity >= self.config.warning_threshold:
            bridge_result.system_message = self._format_pre_tool_message(
                result.severity,
                result.issues,
                should_block,
            )

        # Block session if critical
        if should_block and result.block_reason:
            self.sessions.block(session_id, result.block_reason)

        if self.config.log_detections and result.severity > 0:
            logger.info(
                f"PreToolUse detection: tool={tool_name} "
                f"severity={result.severity} block={should_block} "
                f"time={execution_time_ms:.1f}ms"
            )

        return bridge_result

    async def analyze_post_tool(
        self,
        hook_input: HookInput,
        tool_use_id: Optional[str] = None,
    ) -> BridgeResult:
        """Analyze tool call after execution (PostToolUse).

        This captures the result and may inject recovery messages
        if issues are detected.

        Args:
            hook_input: Input data from Agent SDK (includes tool_response)
            tool_use_id: Unique tool invocation ID

        Returns:
            BridgeResult with recovery message if needed
        """
        start_time = time.perf_counter()
        tool_name = hook_input.get("tool_name", "")

        if not self._should_analyze(tool_name):
            return BridgeResult(execution_time_ms=0)

        session_id = hook_input.get("session_id", "unknown")

        # Convert to span (with response)
        span = self.converter.to_span(hook_input, tool_use_id, is_post=True)

        # Always add to session history
        self.sessions.add_span(session_id, span)

        if not self.config.enable_recovery:
            return BridgeResult(
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        # Get context for analysis
        context = self.sessions.get_context(
            session_id, window=self.config.context_window
        )

        # Run detection (with timeout)
        try:
            result = await asyncio.wait_for(
                self.orchestrator.analyze_realtime(span, context),
                timeout=self.config.detection_timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            return BridgeResult(
                timed_out=True,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Generate recovery message if issues detected
        system_message = None
        if result.severity >= self.config.warning_threshold:
            system_message = self._format_post_tool_message(
                result.severity,
                result.issues,
                result.recommendations,
            )

        if self.config.log_detections and result.severity > 0:
            logger.info(
                f"PostToolUse detection: tool={tool_name} "
                f"severity={result.severity} time={execution_time_ms:.1f}ms"
            )

        return BridgeResult(
            should_block=False,  # Post-tool never blocks
            severity=result.severity,
            issues=result.issues,
            recommendations=self._extract_recommendations(result),
            execution_time_ms=execution_time_ms,
            system_message=system_message,
        )

    def _should_analyze(self, tool_name: str) -> bool:
        """Check if tool should be analyzed.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool should be analyzed
        """
        # Check exclusions first
        for pattern in self._exclude_patterns:
            if pattern.match(tool_name):
                return False

        # Check inclusions
        for pattern in self._include_patterns:
            if pattern.match(tool_name):
                return True

        return False

    def _extract_recommendations(self, result: RealtimeResult) -> list[str]:
        """Extract recommendation strings from result.

        Args:
            result: Detection result

        Returns:
            List of recommendation strings
        """
        recommendations = []
        for rec in result.recommendations:
            if isinstance(rec, dict) and "fix_instruction" in rec:
                recommendations.append(rec["fix_instruction"])
            elif isinstance(rec, str):
                recommendations.append(rec)
        return recommendations

    def _format_pre_tool_message(
        self,
        severity: int,
        issues: list[str],
        blocked: bool,
    ) -> str:
        """Format system message for PreToolUse.

        Args:
            severity: Detection severity
            issues: List of issues detected
            blocked: Whether the tool was blocked

        Returns:
            Formatted message string
        """
        issue_text = "\n".join(f"- {i}" for i in issues[:3])

        if blocked:
            return f"""[MAO Detection: BLOCKED]
Severity: {severity}/100

Issues detected:
{issue_text}

This tool call has been blocked. Please try a different approach.
Consider: stopping repetitive patterns, changing strategy, or asking the user for guidance."""
        else:
            return f"""[MAO Detection: Warning]
Severity: {severity}/100

Issues detected:
{issue_text}

Consider adjusting your approach to avoid potential failure patterns."""

    def _format_post_tool_message(
        self,
        severity: int,
        issues: list[str],
        recommendations: list[Any],
    ) -> str:
        """Format system message for PostToolUse recovery.

        Args:
            severity: Detection severity
            issues: List of issues detected
            recommendations: List of recommendations

        Returns:
            Formatted message string
        """
        issue_text = "\n".join(f"- {i}" for i in issues[:3])

        rec_text = ""
        if recommendations:
            rec_lines = []
            for r in recommendations[:2]:
                if isinstance(r, dict) and "fix_instruction" in r:
                    rec_lines.append(r["fix_instruction"])
                elif isinstance(r, str):
                    rec_lines.append(r)
            if rec_lines:
                rec_text = "\n\nRecommended actions:\n" + "\n".join(
                    f"- {r}" for r in rec_lines
                )

        return f"""[MAO Detection: Recovery Guidance]
Severity: {severity}/100

Pattern detected:
{issue_text}
{rec_text}

Adjust your approach to prevent this pattern from continuing."""

    def _format_blocked_message(self, session_id: str) -> str:
        """Format message for blocked session.

        Args:
            session_id: Session identifier

        Returns:
            Formatted message string
        """
        reason = self.sessions.get_block_reason(session_id) or "repeated violations"

        return f"""[MAO Detection: Session Blocked]
This session has been blocked due to: {reason}

To continue, the user must acknowledge and reset the session."""


# Module-level bridge instance
_default_bridge: Optional[DetectionBridge] = None


def get_bridge() -> DetectionBridge:
    """Get or create the default detection bridge.

    Returns:
        DetectionBridge instance
    """
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = DetectionBridge()
    return _default_bridge


def configure_bridge(
    warning_threshold: int = 40,
    block_threshold: int = 60,
    timeout_ms: float = 80,
    enable_blocking: bool = True,
    enable_recovery: bool = True,
) -> DetectionBridge:
    """Configure and return the default detection bridge.

    Call this before using hooks to customize behavior.

    Args:
        warning_threshold: Severity to trigger warnings
        block_threshold: Severity to trigger blocking
        timeout_ms: Detection timeout in milliseconds
        enable_blocking: Whether to allow blocking
        enable_recovery: Whether to inject recovery messages

    Returns:
        Configured DetectionBridge instance
    """
    global _default_bridge
    config = BridgeConfig(
        warning_threshold=warning_threshold,
        block_threshold=block_threshold,
        detection_timeout_ms=timeout_ms,
        enable_blocking=enable_blocking,
        enable_recovery=enable_recovery,
    )
    _default_bridge = DetectionBridge(config=config)
    return _default_bridge


def create_bridge(
    warning_threshold: int = 40,
    block_threshold: int = 60,
    timeout_ms: float = 80,
    enable_blocking: bool = True,
) -> DetectionBridge:
    """Create a new detection bridge with custom configuration.

    Unlike configure_bridge, this creates a new instance without
    affecting the default bridge.

    Args:
        warning_threshold: Severity to trigger warnings
        block_threshold: Severity to trigger blocking
        timeout_ms: Detection timeout in milliseconds
        enable_blocking: Whether to allow blocking

    Returns:
        New DetectionBridge instance
    """
    config = BridgeConfig(
        warning_threshold=warning_threshold,
        block_threshold=block_threshold,
        detection_timeout_ms=timeout_ms,
        enable_blocking=enable_blocking,
    )
    return DetectionBridge(config=config)
