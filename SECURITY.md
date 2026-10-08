# Security Policy

## Supported Versions

ASUR is in early development (Phase 1). Security fixes are applied to the latest
released version on the `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## ASUR's Security Posture

ASUR is **local-first and key-free by design** (invariant ASUR-LOCAL-01). The core
package:

- makes **no network calls**,
- requires **no API keys or cloud credentials**, and
- depends on the **Python standard library only**.

This architecture removes entire classes of vulnerabilities (credential leakage,
server-side request forgery, supply-chain risk from runtime dependencies). The most
security-relevant surfaces are therefore:

- the **GENERATION ↔ VIRAL CHECK firewall** (invariant ASUR-FIREWALL-01), which must
  fail closed and must never leak target names across the boundary;
- **provenance and versioning** of assets (ASUR-PROV-01, ASUR-VERSION-01); and
- the optional `[generation]` extra, which pulls in third-party media dependencies.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately by one of the following methods:

1. **Preferred:** Use GitHub's [private vulnerability reporting][gh-advisory] via the
   repository's **Security** tab → **Report a vulnerability**.
2. **Email:** Send details to **prathamshukla2804@gmail.com** with the subject line
   `[ASUR SECURITY]`.

Please include, where possible:

- a description of the vulnerability and its impact,
- the affected component (e.g. firewall, versioning, a specific module),
- steps to reproduce or a proof of concept,
- any suggested remediation.

## What to Expect

- **Acknowledgement** within 5 business days.
- An initial **assessment** and severity triage within 10 business days.
- Coordinated disclosure: we will work with you on a fix and a disclosure timeline,
  and will credit you in the changelog unless you prefer to remain anonymous.

## Scope

In scope:

- The ASUR core package and its firewall, versioning, and provenance guarantees.
- CI workflows and anything that could compromise the build or release integrity.

Out of scope:

- Vulnerabilities in third-party dependencies pulled by the optional `[generation]`
  extra (please report those upstream), unless ASUR uses them in an unsafe way.
- Issues requiring a compromised local machine or privileged local access, since ASUR
  explicitly trusts the local operator (invariant ASUR-HUMAN-01).

[gh-advisory]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
