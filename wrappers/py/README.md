# diagnos

**The diagnos vault from Python — zero-knowledge SDK, command line and REST API, in one package.**

**English** · [Português (Brasil)](README.pt-BR.md)

[![PyPI](https://img.shields.io/pypi/v/diagnos?color=3776ab)](https://pypi.org/project/diagnos/)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](https://pypi.org/project/diagnos/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-64748b)](https://github.com/diagnos-tech/integration/blob/main/LICENSE)

Everything clinical is encrypted **inside your process** before it touches the network — the vault only ever sees
ciphertext. One package carries every way in; you install only the layers you use.

## Install what you need

| You want | Install | You get |
|---|---|---|
| A first look | `pip install diagnos` | `diagnos docs`, `version`, `setup`, `help` — no dependencies at all |
| The SDK, in your code | `pip install "diagnos[sdk]"` | `from diagnos import Diagnos` |
| The command line | `pip install "diagnos[cli]"` | `diagnos login`, `diagnos patients list`, … |
| The REST API | `pip install "diagnos[api]"` | `diagnos-api` — FastAPI with mandatory mTLS |

Extras combine (`"diagnos[cli,api]"`). Two more sit on top: `openbao` (OpenBao auto-unseal for servers) and
`dev-certs` (`diagnos-api dev-certs`, local certificates). With [uv](https://docs.astral.sh/uv/):
`uv add "diagnos[sdk]"` in a project, `uv tool install "diagnos[cli]"` for the command line. The REST API also
ships as a signed container image: `ghcr.io/diagnos-tech/diagnos-api`.

Python 3.11 to 3.13, on Linux (glibc and musl, x86_64 and arm64), macOS (Apple silicon and Intel) and Windows
(x86_64). Every wheel carries the prebuilt Rust memory enclave — no compiler needed.

## Let `diagnos` set it up

The base install knows how to install the rest, step by step:

```sh
uv tool install diagnos   # or: pipx install diagnos
diagnos setup sdk         # adds the SDK to the Python project in this folder (uv)
diagnos setup cli         # gives this `diagnos` every command (uv)
diagnos setup api         # pulls the API image and verifies its signature (Docker, cosign)
```

Every command is shown before it runs and confirmed once. `--dry-run` only prints the plan; `--yes` runs it without
asking, for scripts. A missing tool (`uv`, Docker) is never installed for you: `setup` says where to get it and exits
with `69`.

## The base commands

| Command | Does |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lists the Help Center, Developer Central and Trust Center, or prints (or opens) one |
| `diagnos version [--json]` | This installation: version, interpreter, platform and which extras are in |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Installs one layer, step by step |
| `diagnos help [command]` | The overview, or one command's options |

Once `diagnos[cli]` is installed, `diagnos` is the full command line and still answers these four. Exit codes: `0`
success, `1` a step failed or was declined, `2` usage error, `69` something this needs is not installed.

## Quick start

```python
from diagnos import Diagnos

with Diagnos() as vault:  # enrolls on entry: prints the approval link + code
    print(vault.security_groups)
```

Set `DIAGNOS_CREDENTIAL` first — a workspace admin creates it in the diagnos web app (Settings → Service accounts). The
[quickstart](https://github.com/diagnos-tech/integration/blob/main/docs/guides/quickstart.md) goes from here to
your first encrypted patient and file.

## Verify what you install

Every release is built by one GitHub Actions workflow and signed there, keylessly, with
[Sigstore](https://www.sigstore.dev/). PyPI shows each file's provenance; the same files, their `.sigstore.json`
bundles and `SHA256SUMS` are attached to the
[GitHub release](https://github.com/diagnos-tech/integration/releases). With `cosign`:

```sh
cosign verify-blob diagnos-0.1.0.tar.gz \
  --bundle diagnos-0.1.0.tar.gz.sigstore.json \
  --certificate-identity "https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v0.1.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"

cosign verify ghcr.io/diagnos-tech/diagnos-api:0.1.0 \
  --certificate-identity "https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v0.1.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

Or with the GitHub CLI: `gh attestation verify diagnos-0.1.0.tar.gz --repo diagnos-tech/integration`.

## Learn more

- **Help Center** — <https://docs.diagnos.health>
- **Developer Central** — <https://dev.diagnos.health>
- **Trust Center** — <https://trust.diagnos.health>
- **Source, issues and changelog** — <https://github.com/diagnos-tech/integration>

Licensed under [Apache-2.0](https://github.com/diagnos-tech/integration/blob/main/LICENSE). Report a vulnerability
privately through [GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new).
