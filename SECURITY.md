# Security Policy

**English** · [Português (Brasil)](SECURITY.pt-BR.md)

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability, even a suspected one. Report it privately
through **[GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new)**.

That form goes only to the maintainers. We will acknowledge your report, work with you to understand and confirm
it, and keep you updated as we prepare a fix. We do not have a bug bounty program at this time.

Vulnerabilities in the vault service itself (`https://vault.diagnos.health`) — as opposed to these client
packages — are reported through the same channel: open a
[private security advisory](https://github.com/diagnos-tech/integration/security/advisories/new) here rather than
contacting the vault separately, and the maintainers will route it internally.

## Supported versions

| Version | Supported |
|---|---|
| latest `0.1.x` | ✅ |
| anything earlier | ❌ |

`diagnos`, `diagnos-cli` and `diagnos-api` are versioned and released together; "latest `0.1.x`" means the most
recent tag published across all three. Only the latest release receives security fixes while the project is at
`0.x` — there is no long-term support branch yet.

## Scope

In scope:

- **The SDK's cryptography** (`sdk/src/diagnos/crypto/`) — key derivation, hybrid sealing, content encryption,
  request signing, and anywhere a wire format from `docs/PROTOCOL.md` is implemented.
- **The Rust memory enclave** (`sdk/native`) — the code responsible for keeping session keys, DEKs and private keys
  out of swap, core dumps and `fork()` children. See [`sdk/native/README.md`](sdk/native/README.md) for the enclave's
  threat model: what it guarantees, what it explicitly does not (root/`CAP_SYS_PTRACE`, code running in the same
  process, the OpenBao export window, Windows), and where the `unsafe` blocks live.
- **The CLI** (`cli/`) — argument parsing, credential handling, anything that could leak a token or decrypted
  content to a log, a file, or the wrong file descriptor.
- **The API** (`api/`), including its mutual TLS handling — certificate validation, allowed-CN enforcement, and the
  deploy manifests under `api/deploy/` (Docker Compose, Kubernetes, OpenBao bootstrap and auto-unseal
  configuration).

Out of scope: vulnerabilities that require an attacker to already have root, `CAP_SYS_PTRACE`, or code execution in
the same process as the SDK — the enclave's threat model documents these as accepted limits, not bugs. See
[`sdk/native/README.md`](sdk/native/README.md) before reporting one of these.

## What to include in a report

To help us triage and fix the issue quickly, please include as much of the following as you can:

- The affected package(s) and version(s) (`diagnos`, `diagnos-cli`, `diagnos-api`, or a deploy manifest).
- A description of the vulnerability and its impact (what an attacker gains, and what they need to exploit it).
- Steps to reproduce, or a minimal proof-of-concept (code, request/response pair, or manifest diff).
- The Python version, operating system, and — for the enclave — whether `CAP_IPC_LOCK` / `mlock` succeeded
  (`memory_status()`), since some enclave protections degrade gracefully and that matters for severity.
- Any suggested fix or mitigation, if you have one.

You do not need to have a fix ready to report something — a clear description of the problem is enough to start.
