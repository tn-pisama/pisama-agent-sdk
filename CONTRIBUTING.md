# Contributing to pisama-agent-sdk

Thanks for your interest in improving `pisama-agent-sdk`. This package
provides Claude Agent SDK hooks for real-time failure detection —
flagging loops, hallucinations, and other failures before they burn
tokens. Core detection engine lives in
[`pisama-core`](https://github.com/tn-pisama/pisama-core);
advanced detectors and calibrated thresholds live in
[Pisama](https://pisama.ai) Cloud.

## What we're looking for

- **New hook points** for agent lifecycle events that Claude Agent SDK
  exposes (pre-tool-call, post-tool-call, message-stream, etc.).
- **Framework adapters** for related orchestrators that want the same
  detection surface.
- **Bug reports** with a minimal reproducer — especially cases where
  a hook fails to fire or misclassifies a legitimate retry.
- **Documentation fixes** on the hook matrix and configuration.

## What we're not looking for

- Tuned detection thresholds. Those are Pisama Cloud features.
- Hook paths that auto-terminate agent runs without a documented opt-in.

## Development setup

```bash
git clone https://github.com/tn-pisama/pisama-agent-sdk.git
cd pisama-agent-sdk
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest tests/
```

## PR checklist

- [ ] New hook (if applicable) is registered via the documented hook
      API and disables cleanly when the user opts out.
- [ ] Detection calls go through `pisama_core` — no detection logic
      lives in this package.
- [ ] Clean-venv install succeeds with the declared dependencies.
- [ ] Existing tests pass: `pytest tests/ -q`.

## Licensing and contributor grant

By submitting a PR you agree that your contribution is licensed under
MIT, the same license as this repo.

## Questions

Open a GitHub Discussion or visit [pisama.ai](https://pisama.ai).
