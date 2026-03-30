"""PreToolUse hook implementation."""

import logging
from typing import Any, Optional

from ..bridge import DetectionBridge, get_bridge, create_bridge
from ..types import HookContext, HookInput

logger = logging.getLogger(__name__)


async def pre_tool_use_hook(
    input_data: HookInput,
    tool_use_id: Optional[str],
    context: HookContext,
) -> dict[str, Any]:
    """PreToolUse hook for real-time failure prevention.

    This hook is called before each tool execution and can:
    - Block the tool call by returning permissionDecision: "block"
    - Inject a warning message via systemMessage
    - Allow execution by returning empty dict

    Args:
        input_data: Contains tool_name, tool_input, session_id
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context with signal

    Returns:
        Hook output dict with blocking decision or message

    Example:
        from pisama_agent_sdk.hooks import pre_tool_use_hook

        # Register with Claude Agent SDK
        agent.hooks.pre_tool_use = pre_tool_use_hook
    """
    if not tool_use_id:
        logger.debug("PreToolUse called without tool_use_id, skipping")
        return {}

    bridge = get_bridge()

    try:
        result = await bridge.analyze_pre_tool(input_data, tool_use_id)

        if result.timed_out:
            logger.warning(
                f"Detection timeout for {input_data.get('tool_name')}, "
                f"allowing to proceed"
            )
            return {}

        output = result.to_hook_output()

        if result.should_block:
            logger.info(
                f"Blocking tool {input_data.get('tool_name')} "
                f"(severity={result.severity})"
            )

        return output

    except Exception as e:
        logger.error(f"PreToolUse hook error: {e}", exc_info=True)
        # Fail open - don't block on errors
        return {}


class PreToolUseHook:
    """Class-based PreToolUse hook with configuration.

    Use this when you need more control over the hook behavior,
    such as custom bridge configuration or fail behavior.

    Example:
        from pisama_agent_sdk.hooks import PreToolUseHook
        from pisama_agent_sdk import create_bridge, BridgeConfig

        # Custom configuration
        config = BridgeConfig(warning_threshold=30, block_threshold=50)
        bridge = DetectionBridge(config=config)

        # Create hook with custom bridge
        hook = PreToolUseHook(bridge=bridge, fail_open=True)

        # Register with agent
        agent.hooks.pre_tool_use = hook
    """

    def __init__(
        self,
        bridge: Optional[DetectionBridge] = None,
        fail_open: bool = True,
    ) -> None:
        """Initialize the hook.

        Args:
            bridge: Custom detection bridge (defaults to global)
            fail_open: If True, allow execution on hook errors
        """
        self.bridge = bridge or get_bridge()
        self.fail_open = fail_open

    async def __call__(
        self,
        input_data: HookInput,
        tool_use_id: Optional[str],
        context: HookContext,
    ) -> dict[str, Any]:
        """Handle PreToolUse event.

        Args:
            input_data: Hook input data
            tool_use_id: Tool use identifier
            context: Hook context

        Returns:
            Hook output dict
        """
        if not tool_use_id:
            return {}

        try:
            result = await self.bridge.analyze_pre_tool(input_data, tool_use_id)
            return result.to_hook_output()
        except Exception as e:
            logger.error(f"PreToolUse error: {e}")
            if self.fail_open:
                return {}
            raise
