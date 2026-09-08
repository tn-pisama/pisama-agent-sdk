# Changelog

## [0.4.1] - 2026-09-08

### Fixed

- Replace the retired documentation link with the canonical public README.
- Defang the retired hostname in the historical security disclosure so it
  cannot be followed or copied as a working endpoint. The warning and affected
  version history remain included in the source distribution.
- Update the pinned publisher for core metadata 2.5 support. Validation,
  attestations and the eight artifact-install checks remain enabled.

No runtime implementation, forwarding behavior or dependency floor changed.
This release does not modify older installed artifacts or prove that exposed
credentials used with older clients have been revoked.

## [0.4.0] - 2026-07-29

### Changed

- **This package is now a thin shim.** Every module (`atif.py`,
  `bridge.py`, `check.py`, `check_compliance.py`, `clarification.py`,
  `config.py`, `converter.py`, `evaluator.py`, `heal.py`,
  `indication.py`, `openhands_adapter.py`, `session.py`, `tools.py`,
  `types.py`, `hooks/*`, `chaos/*`, `cli/*`) now re-exports the
  equivalent object from `pisama.agents.*` — the original code that used
  to live in this distribution moved to the `pisama` base package
  (`pisama-python`, published as `pisama` on PyPI, `pisama.agents`
  submodule) as of `pisama` 0.6.0. This is a real per-path forward, not
  a single flat `from pisama.agents import *`: deep imports like
  `pisama_agent_sdk.hooks.pre_tool_use.pre_tool_use_hook` keep working
  because `hooks/pre_tool_use.py` is itself a forwarding module, not
  just a name reachable off the package root.
- `dependencies` is now `["pisama>=0.6.0"]`, replacing
  `pisama-core>=1.7.3,<2`. This package no longer imports `pisama_core`
  directly at all — `pisama` depends on it transitively.
- **`__version__` stays this distribution's own version** (`0.4.0`),
  *not* aliased to `pisama.__version__` the way `pisama.agents.
  __version__` is. `pisama.agents` doesn't release independently
  anymore, so tracking the base package's version is correct there.
  This package still cuts its own PyPI releases, and a caller checking
  `pisama_agent_sdk.__version__` reasonably expects it to reflect the
  installed `pisama-agent-sdk` release they asked pip for. Judgment
  call, documented in `src/pisama_agent_sdk/__init__.py`.
- **Extras (`evaluator`, `telemetry`) are unchanged in content** —
  still `httpx>=0.24` and `posthog>=3.0` respectively, declared
  directly rather than as `pisama[agents]` / `pisama[telemetry]`. Two
  reasons: (1) the cycle rule below applies to any dependency edge from
  this package onto a bracketed `pisama[...]` extra, not just the base
  `dependencies` list, and depending on `pisama`'s own extra names
  would couple this package's extras to naming decisions made in a
  different repo's release cadence for no benefit; (2) `pisama`'s
  `agents` extra is *already* just `httpx>=0.24` with nothing else in
  it, so there's nothing to gain by indirecting through it. In
  practice, `evaluator` is now a no-op: `pisama>=0.6.0` hard-depends on
  `httpx>=0.27` unconditionally, so `analyze_atif()` / `PisamaEvaluator`
  work regardless of whether `[evaluator]` was requested. This is a
  user-visible (strictly more permissive, never breaking) behavior
  change from 0.3.x, where omitting `[evaluator]` meant those calls
  raised `ImportError`. `telemetry` keeps gating real behavior: posthog
  stays a `try`/`except ImportError`-guarded optional import inside
  `DetectionBridge`.
- `auto_verify` stays removed (0.3.0). It vendored private backend
  verification primitives into this MIT package — a real prior
  incident — and was correctly not mirrored into `pisama.agents`
  either. There was nothing left to forward; no references to it
  remain anywhere in this repo.
- The `pisama-openhands-monitor` console script keeps its entry point
  (`pisama_agent_sdk.cli.openhands_monitor:main`) but that path is now
  a two-line forwarder to `pisama.agents.cli.openhands_monitor:main`.

### Why

`pisama` 0.6.0 shipped `pisama.auto` and `pisama.agents` as original
code, consolidating what used to be separately-maintained standalone
packages (`pisama-auto`, `pisama-agent-sdk`) into one repo. Nothing on
PyPI is unpublished by this change — 0.1.1 through 0.3.1 (and whatever
ships as 0.3.2) stay exactly as they were. This release makes
`pisama-agent-sdk` a permanent compatibility layer on top of the
consolidated implementation so `import pisama_agent_sdk` keeps working
without a code change on the caller's side, forever, while all future
bug fixes and features land once in `pisama.agents` instead of being
duplicated across two codebases.

**Cycle rule:** this package depends on `pisama>=0.6.0` (the base
package), never on `pisama[auto]` or `pisama[agents]` (the extras).
Depending on a `pisama` extra that itself depended back on
`pisama-agent-sdk` would be a real dependency cycle; today neither
`pisama[auto]` nor `pisama[agents]` does that, but the direction is
worth holding as an invariant rather than re-deriving it each release.

## [0.3.2] - 2026-07-29

### Fixed

- The README linked the Claude Agent SDK at
  `github.com/anthropics/claude-code/tree/main/packages/claude-agent-sdk`, which
  returns 404. Upstream moved the Python SDK to its own repository. The link now
  points at `github.com/anthropics/claude-agent-sdk-python`, which is also the
  `Homepage` in the `claude-agent-sdk` PyPI metadata. PyPI renders the README from
  the published artifact, so this needs a release to reach the people who read it.

### Changed

- Declare the licence as the PEP 639 SPDX expression `license = "MIT"` with
  `license-files = ["LICENSE"]`, replacing the deprecated `{text = "MIT"}` table.
  The wheel now carries `License-Expression: MIT` and `License-File: LICENSE`
  instead of the free-text `License` field.
- Drop the `License :: OSI Approved :: MIT License` trove classifier. The
  `pyproject.toml` specification deprecates `License ::` classifiers and permits
  build tools to reject a project that sets both them and an SPDX expression;
  setuptools already errors on that combination. The licence is not lost, it moves
  into `License-Expression`.
- Require `hatchling>=1.27` to build, the first release line that emits core
  metadata 2.4 and reads `license-files` as a list of glob patterns.

## [0.3.1] - 2026-07-29

### Security

- `PisamaEvaluator` defaulted `base_url` to the retired `mao-api[.]fly[.]dev`
  hostname (defanged for safety; do not use as an endpoint), a pre-rebrand
  Fly.io hostname that is no longer a deployed app. Fly app names are globally unique
  and become claimable once released, so any third party could have created an app of
  that name and received the `api_key` this client sets as a default header on every
  request. The default is now `https://api.pisama.ai`.

### Fixed

- Authenticate with `Authorization: Bearer` instead of the legacy `X-MAO-API-Key`
  header. That header is not read anywhere in the current backend, and
  `POST /api/v1/evaluate` declares `HTTPBearer`, so requests could not have succeeded
  against the live API regardless of host.

## Unreleased

## 0.2.1

- Add a full-package coverage regression gate and security scanning.
- Declare the MIT license classifier in package metadata.
- Document ATIF, OpenHands, and Harbor-compatible evaluation use cases.
- Add typed-package metadata, mypy checks, dependency automation, distribution
  inspection, and clean-wheel smoke testing.
- Correct nullable endpoint handling and the clarification provider type
  contract.
- Refresh build, lint, publishing, and GitHub Actions tooling while preserving
  broad compatibility for optional runtime dependencies.
- Raise full-package coverage from 61.53% to more than 70% with real
  pisama-core detector runs and captured Harbor tool calls.
- Fix `check()` local detection against the current pisama-core Span contract;
  it previously failed silently and fell through to the network API.
- Make `BridgeConfig.save()` output loadable by `BridgeConfig.from_file()`.
- Support the documented `configure_bridge(BridgeConfig(...))` call and
  matcher filtering on `PreToolUseHook`.
- Constrain pisama-core to its compatible major version.
- Add Python 3.13 support metadata and release coverage.
- Pin release actions and stabilize lint configuration.

## 0.2.0

- Add ATIF v1.7 analysis support.
- Add the OpenHands session monitor command.
- Test package installation and public APIs on Python 3.10 through 3.13.

## 0.1.1

- Improve package metadata and release automation.
