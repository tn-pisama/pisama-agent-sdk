# pisama-agent-sdk

Real-time failure detection hooks for the [Claude Agent SDK](https://github.com/anthropics/claude-code/tree/main/packages/claude-agent-sdk). Catches infinite loops, hallucinations, and other failure modes before they cause damage.

Part of the [Pisama](https://pisama.dev) platform for multi-agent failure detection.

## Install

```bash
pip install pisama-agent-sdk
```

## Quick Start

### Passive Monitoring (hooks)

Add two lines to your Claude Agent SDK setup:

```python
from pisama_agent_sdk import pre_tool_use_hook, post_tool_use_hook

agent.hooks.pre_tool_use = pre_tool_use_hook
agent.hooks.post_tool_use = post_tool_use_hook
```

Every tool call is now checked for failure patterns in real-time (<100ms). If a loop or other issue is detected, the hook returns a blocking signal to stop the agent.

### Active Self-Check

Let the agent verify its own output:

```python
from pisama_agent_sdk import check

result = await check(
    output="The server is healthy based on the metrics.",
    context={"query": "Is auth-service down?", "sources": [...]},
)
if not result["passed"]:
    # result["issues"] describes what went wrong
    print(result["issues"])
```

### Custom Tool for Claude Agent SDK

Give the agent a tool it can call to self-check:

```python
from pisama_agent_sdk import create_check_tool
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    custom_tools=[create_check_tool()],
)
```

## Configuration

```python
from pisama_agent_sdk import configure_bridge, BridgeConfig

configure_bridge(BridgeConfig(
    fail_open=True,           # Allow execution if detection errors (default: True)
    detection_timeout_ms=80,  # Max detection time per hook (default: 80)
))
```

## Tool Matchers

Control which tools get checked:

```python
from pisama_agent_sdk import PreToolUseHook, create_matcher, FILE_TOOLS, SHELL_TOOLS

# Only check file and shell tools
hook = PreToolUseHook(matcher=create_matcher(include=[FILE_TOOLS, SHELL_TOOLS]))
agent.hooks.pre_tool_use = hook
```

Built-in matchers: `ALL_TOOLS`, `FILE_TOOLS`, `SHELL_TOOLS`, `DANGEROUS_COMMANDS`, `AGENT_TOOLS`.

## How It Works

1. Your agent makes a tool call
2. `pre_tool_use_hook` converts the call into a Pisama `Span`
3. Registered detectors run against the span + recent session context
4. If a failure is detected (e.g., 5th consecutive `Read` of the same file), the hook returns a blocking result
5. The agent receives the block signal and adjusts its behavior

Detection runs entirely locally using `pisama-core` detectors. No network calls unless you configure a remote endpoint.

## Evaluator Mode

Use Pisama as an evaluator in multi-agent harnesses:

```python
from pisama_agent_sdk import PisamaEvaluator

evaluator = PisamaEvaluator(endpoint="https://your-pisama-instance/api/v1")
result = await evaluator.evaluate(trace_data)
print(result.passed, result.failures)
```

Requires `pip install pisama-agent-sdk[evaluator]`.

## License

MIT
