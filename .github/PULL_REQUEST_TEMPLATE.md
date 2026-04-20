## What this changes

<!-- 1–3 sentences. What's different after this PR and why. -->

## Type

- [ ] New hook point
- [ ] Framework adapter
- [ ] Bug fix (hook missing a call path, false-positive/negative, etc.)
- [ ] API change
- [ ] Docs

## Checklist

- [ ] Clean-venv install works: `pip install .` in a fresh env, the
      affected hook fires on a sample agent run.
- [ ] Detection calls go through `pisama_core` — no detection logic
      lives in this package.
- [ ] New hooks disable cleanly when the user opts out.
- [ ] Existing tests pass: `pytest tests/ -q`.
- [ ] README hook matrix updated if a new hook point is added.

## Reproducer or before/after (for bug fixes)

```python
# Before: ...
# After: ...
```
