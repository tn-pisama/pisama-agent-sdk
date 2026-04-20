# Security Policy

## Reporting a vulnerability

If you've found a security issue in `pisama-agent-sdk`, please do
**not** open a public GitHub issue. Instead:

- Email **security@pisama.ai** with a description, reproducer, and
  the affected version.
- We'll acknowledge within 2 business days and aim to ship a fix or
  mitigation within 7 business days for high-severity issues.

## What counts as a security issue

- A hook path allowing attacker-controlled agent output to bypass
  detection or suppress a flagged failure.
- Telemetry payload leaking beyond the configured endpoint.
- Dependency vulnerabilities that affect the hook surface.

## Supported versions

Only the latest 0.x release line is supported. When 1.0 ships we'll
document an LTS policy.

## Credit

We'll credit reporters in release notes unless you prefer to stay
anonymous.
