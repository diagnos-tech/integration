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

`diagnos` is one package — the base and its `sdk`, `cli` and `api` extras — published to PyPI together with the
`ghcr.io/diagnos-tech/diagnos` and `ghcr.io/diagnos-tech/diagnos-api` images, all under one version. Only the latest
release receives security fixes while the project is at `0.x` — there is no long-term support branch yet.

## Scope

In scope:

- **The SDK's cryptography** (`src/diagnos/crypto/`) — key derivation, hybrid sealing, content encryption,
  request signing, and anywhere a wire format from `docs/PROTOCOL.md` is implemented.
- **The Rust memory enclave** (`apps/sdk/native`) — the code responsible for keeping session keys, DEKs and private keys
  out of swap, core dumps and `fork()` children. See [`apps/sdk/native/README.md`](apps/sdk/native/README.md) for the enclave's
  threat model: what it guarantees, what it explicitly does not (root/`CAP_SYS_PTRACE`, code running in the same
  process, the OpenBao export window, Windows), and where the `unsafe` blocks live.
- **The base** (`src/diagnos/_wrapper/`, `src/diagnos/_entry.py`) — `diagnos setup` runs `uv`, Docker and cosign
  on your behalf; anything that runs a program the user did not see, runs it from an unexpected path, or verifies an
  image less strictly than documented below.
- **The CLI** (`src/diagnos/cli/`) — argument parsing, credential handling, anything that could leak a token or decrypted
  content to a log, a file, or the wrong file descriptor.
- **The API** (`src/diagnos/api/`), including its mutual TLS handling — certificate validation, allowed-CN enforcement, and the
  deploy manifests under `apps/api/deploy/` (Docker Compose, Kubernetes, OpenBao bootstrap and auto-unseal
  configuration).
- **The release pipeline and images** — `.github/workflows/`, the `Dockerfile`, and anything that could let a
  build, a signature or a published file differ from what this repository's code and lockfiles say.

Out of scope: vulnerabilities that require an attacker to already have root, `CAP_SYS_PTRACE`, or code execution in
the same process as the SDK — the enclave's threat model documents these as accepted limits, not bugs. See
[`apps/sdk/native/README.md`](apps/sdk/native/README.md) before reporting one of these.

## Verifying a release

Every release is built and signed by one workflow — `.github/workflows/release.yml`, run for the release's tag —
keylessly, with [Sigstore](https://www.sigstore.dev/). **We never publish with an API token or a stored key**: a
`diagnos` distribution without PEP 740 provenance on PyPI, or a file or image whose signature does not name exactly
that workflow at that tag, is not ours — please report it. You need [cosign](https://docs.sigstore.dev/cosign/system_config/installation/)
3.1.3 or later (older versions have a verification bypass, GHSA-fx35-mq7g-6g98) or the [GitHub CLI](https://cli.github.com/).

```sh
V=0.1.0
ID="https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v$V"
ISSUER="https://token.actions.githubusercontent.com"

# The files of the GitHub release: the checksums are signed, every file is in the checksums.
gh release download "v$V" --repo diagnos-tech/integration --dir "diagnos-$V" && cd "diagnos-$V"
cosign verify-blob --bundle SHA256SUMS.sigstore.json --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER" SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS     # macOS: shasum -a 256 --check --ignore-missing SHA256SUMS

# One file — including a wheel you downloaded from PyPI — on its own.
cosign verify-blob --bundle "diagnos-$V.tar.gz.sigstore.json" --certificate-identity "$ID" \
  --certificate-oidc-issuer "$ISSUER" "diagnos-$V.tar.gz"
gh attestation verify "diagnos-$V.tar.gz" --repo diagnos-tech/integration --cert-identity "$ID"

# The images, by the digest you will run.
cosign verify "ghcr.io/diagnos-tech/diagnos-api@sha256:<digest>" --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER"
gh attestation verify "oci://ghcr.io/diagnos-tech/diagnos-api@sha256:<digest>" --repo diagnos-tech/integration --cert-identity "$ID"
```

Always pin the identity (`--certificate-identity` / `--cert-identity`): `gh attestation verify --repo` alone accepts
an attestation from any branch of the repository. To accept any release instead of one version, use an anchored
`--certificate-identity-regexp '^https://github\.com/diagnos-tech/integration/\.github/workflows/release\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+$'`.
`images.txt` in each GitHub release lists the two image digests, signed the same way; `diagnos setup api` runs the
image check for you and prints the `docker run` by the verified digest. Each release also carries its SLSA
provenance as `diagnos-$V.intoto.jsonl`, for checks without GitHub's API
(`gh attestation verify "$FILE" --bundle "diagnos-$V.intoto.jsonl" --repo diagnos-tech/integration --cert-identity "$ID"`),
and a CycloneDX SBOM of its Python dependencies, `diagnos-$V.cdx.json`, signed like every other file.

## What to include in a report

To help us triage and fix the issue quickly, please include as much of the following as you can:

- The affected layer and version (`diagnos` and which extras, an image, the release pipeline, or a deploy
  manifest) — `diagnos version --json` prints it.
- A description of the vulnerability and its impact (what an attacker gains, and what they need to exploit it).
- Steps to reproduce, or a minimal proof-of-concept (code, request/response pair, or manifest diff).
- The Python version, operating system, and — for the enclave — whether `CAP_IPC_LOCK` / `mlock` succeeded
  (`memory_status()`), since some enclave protections degrade gracefully and that matters for severity.
- Any suggested fix or mitigation, if you have one.

You do not need to have a fix ready to report something — a clear description of the problem is enough to start.
