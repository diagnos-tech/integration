# Migrating

**English** · [Português (Brasil)](MIGRATING.pt-BR.md)

Two migrations, newest first: from the `apikey-` token to a service account credential (`0.2.0`), and from the former
`imgexam` packages to `diagnos` (`0.1.0`).

## From the `apikey-` token to a service account credential (0.2.0)

`0.2.0` authenticates with a **service account credential**: an Ed25519 key pair born in the browser of whoever
creates it, whose identity reads like an e-mail address — `svc_<32 hex>@<workspace_id>.diagnos.health` — and whose
private key signs every request (HTTP Message Signatures, RFC 9421). The vault keeps only the public key, so nobody,
the vault included, can act as your service account without the file or line you saved. Nothing reusable travels:
each request carries a fresh signature and nonce, and a copied request is refused.

The `apikey-` token keeps working until **2027-04-15**. Until then `diagnos` accepts it and emits a
`LegacyTokenWarning` (a `DeprecationWarning`) pointing at your own line, plus one log line per process; the vault
answers it with `Deprecation`, `Sunset` and `Link` headers. After that date the vault refuses it.

### Three steps

1. **Create the credential.** In the web app, open *Settings → Service accounts*, pick the service account (or create
   one) and create a key. The page shows the credential **once**: copy the `DIAGNOS_CREDENTIAL` line, or download the
   credential file. An existing account can get a new key next to its token — both work while you migrate.
2. **Swap the environment variable.** Replace `DIAGNOS_API_TOKEN` with one of these (the SDK reads them in this
   order):

   | Where | How |
   |---|---|
   | `DIAGNOS_CREDENTIAL` | `export DIAGNOS_CREDENTIAL="svc_…@<workspace_id>.diagnos.health:<key>"` — the one line the page showed |
   | `DIAGNOS_CREDENTIALS_FILE` | the path of the downloaded JSON file (a Kubernetes or Compose secret mounted `0400`) |
   | `~/.config/diagnos/credentials.json` | the downloaded file saved there, `chmod 600` — no variable needed |

   `DIAGNOS_API_TOKEN` still counts if none of the first two is set, so remove it once the new credential works.
3. **Revoke the token.** Back in *Settings → Service accounts*, revoke the old `apikey-` key.

Code that builds `Diagnos()` with no arguments needs no change. Code that passes the token explicitly:

```python no-run
# before (deprecated, works until 2027-04-15)
vault = Diagnos(token=os.environ["DIAGNOS_API_TOKEN"])

# after
vault = Diagnos()  # DIAGNOS_CREDENTIAL, the file variable, or the default file
vault = Diagnos(credential=os.environ["MY_CREDENTIAL"])  # the one-line form from anywhere
vault = Diagnos(credential=Path("/run/secrets/diagnos.json"))
vault = Diagnos.from_env()  # the same as Diagnos(), spelled out
```

### What else changed

| Before (`apikey-`) | After (credential) |
|---|---|
| `Authorization: Bearer apikey-<jwt>` on every request | `Signature-Input` + `Signature` (+ `Content-Digest` with a body); no `Authorization` |
| `vault.account_id` — the account id from the token | `None`: the identity is the key (`vault.identity`, `vault.key_id`) |
| OpenBao path `<prefix>/<workspace_id>/<account_id>` | `<prefix>/<workspace_id>/<key_id>` — the first unlock after switching enrolls once |
| a revoked or wrong token: `AuthenticationError` | `CredentialRevokedError`, `CredentialUnknownError`, `ClockSkewError`… — all `CredentialError`, each saying what to do |
| `--token apikey-…` (CLI) | the same three sources; `--token` still takes a legacy token |

The session HMAC (`X-Signature-*`), the enrollment (six-digit code, human approval) and everything end-to-end
encrypted are unchanged: the credential replaces only the proof of identity.

### Errors you may meet while migrating

| Exception | What it means | What to do |
|---|---|---|
| `ConfigError` "No diagnos credential found" | none of the three sources is set | set `DIAGNOS_CREDENTIAL` (or the file) |
| `ConfigError` "holds a legacy 'apikey-' token" | the token went into `DIAGNOS_CREDENTIAL` | put it back in `DIAGNOS_API_TOKEN`, or use the new credential |
| `CredentialSignatureError` | the key does not match the identity | copy the credential again, whole |
| `ClockSkewError` | this machine's clock is more than 60 s off; the message shows by how much | turn on automatic time (NTP) |
| `CredentialRevokedError` / `CredentialExpiredError` | the key was revoked or expired | create a new key and swap it in |
| `ScopeMissingError` | the service account lacks a permission (named in the message) | ask a workspace admin to grant it |

## From imgexam (0.1.0)

This project was renamed from `imgexam` to `diagnos`, and its three packages became one, `diagnos`, with extras.
Nothing was published to PyPI under any of the old names. This guide is for anyone who ran an internal or
from-source checkout of the former `imgexam` monorepo, or of the short-lived three-package `diagnos` layout
(packages, a vendored copy, or a deployment built from source), and is moving that checkout to this repository.

`0.1.0` is the first version of `diagnos` ever published — see [`CHANGELOG.md`](CHANGELOG.md). It restarts the
versioning at `0.1.0` regardless of what `imgexam`'s internal version numbers were.

### What changed

#### Packages, modules, classes, exceptions

| Before (`imgexam`) | After (`diagnos`) |
|---|---|
| package `imgexam` | package `diagnos[sdk]` |
| package `imgexam-cli` | package `diagnos[cli]` |
| package `imgexam-api` | package `diagnos[api]` |
| import `imgexam` | import `diagnos` |
| import `imgexam_cli` | import `diagnos.cli` |
| import `imgexam_api` | import `diagnos.api` |
| class `Imgexam` | class `Diagnos` |
| exception `ImgexamError` | exception `DiagnosError` |
| exception `ImgexamPermissionError` | exception `DiagnosPermissionError` |

```python no-run
# before
from imgexam import Imgexam, ImgexamError

# after
from diagnos import Diagnos, DiagnosError
```

#### CLI command and Docker image

| Before | After |
|---|---|
| `imgexam` (command) | `diagnos` (command) |
| `imgexam-api` (Docker image) | `ghcr.io/diagnos-tech/diagnos-api` (Docker image) |

#### From three packages to one

Before `0.1.0` shipped, the project was briefly three packages — `diagnos` (the SDK), `diagnos-cli` and
`diagnos-api`. It is now one, `diagnos`, whose base installs no dependency at all and whose layers are extras. Code
that only does `from diagnos import …` keeps working unchanged, as long as the `sdk` extra is installed.

| Before | After |
|---|---|
| `pip install diagnos` (it was the SDK) | `pip install "diagnos[sdk]"` — plain `diagnos` is now the base, with no dependencies |
| `pipx install diagnos-cli`, `diagnos-cli[openbao]` | `uv tool install "diagnos[cli]"` or `pipx install "diagnos[cli]"`, `diagnos[cli,openbao]` |
| `diagnos-api`, `diagnos-api[dev]` | `diagnos[api]`, `diagnos[dev-certs]` |
| import `diagnos_cli`, `diagnos_api` | import `diagnos.cli`, `diagnos.api` |
| `python -m diagnos_api` | `python -m diagnos.api` (or `diagnos-api`) |
| logger `diagnos_api` | logger `diagnos.api` |
| `docker build -f apps/api/Dockerfile .` | `docker build --target api .` — or the signed `ghcr.io/diagnos-tech/diagnos-api` |
| `uv sync --all-packages`, `uv run --package …` | `uv sync`, `uv run …` — every extra is installed for development |

#### Default vault URL

The default vault URL changed from the previous internal address to `https://vault.diagnos.health`. If you set
`DIAGNOS_VAULT_URL` (see below) explicitly, this does not affect you.

#### Environment variables

Every `IMGEXAM_*` environment variable was renamed to `DIAGNOS_*`, with no other change in meaning or accepted
values:

| Before | After | Where it is read |
|---|---|---|
| `IMGEXAM_API_TOKEN` | `DIAGNOS_API_TOKEN` | SDK (`transport/config.py`, `transport/token.py`), CLI, API |
| `IMGEXAM_VAULT_URL` | `DIAGNOS_VAULT_URL` | SDK (`transport/config.py`), CLI (`--vault-url` override) |
| `IMGEXAM_TIMEOUT_SECONDS` | `DIAGNOS_TIMEOUT_SECONDS` | SDK (`transport/config.py`) |
| `IMGEXAM_SSE_C` | — (removed: files always use SSE-C, like the web app; documents never do) | — |
| `IMGEXAM_HARDEN_PROCESS` | `DIAGNOS_HARDEN_PROCESS` | SDK (`transport/config.py`), Rust enclave (`apps/sdk/native`) |
| `IMGEXAM_MEMORY_LOCK` | `DIAGNOS_MEMORY_LOCK` | Rust enclave (`apps/sdk/native/src/locked/mod.rs`, `error.rs`) |
| `IMGEXAM_API_MTLS_CA_FILE` | `DIAGNOS_API_MTLS_CA_FILE` | API (`diagnos/api/settings.py`), deploy manifests |
| `IMGEXAM_API_TLS_CERT_FILE` | `DIAGNOS_API_TLS_CERT_FILE` | API (`diagnos/api/settings.py`), deploy manifests |
| `IMGEXAM_API_TLS_KEY_FILE` | `DIAGNOS_API_TLS_KEY_FILE` | API (`diagnos/api/settings.py`), deploy manifests |
| `IMGEXAM_API_HOST` | `DIAGNOS_API_HOST` | API (`diagnos/api/settings.py`) |
| `IMGEXAM_API_PORT` | `DIAGNOS_API_PORT` | API (`diagnos/api/settings.py`), deploy manifests |
| `IMGEXAM_API_ALLOWED_CLIENT_CN` | `DIAGNOS_API_ALLOWED_CLIENT_CN` | API (`diagnos/api/settings.py`) |
| `IMGEXAM_WORKSPACE_ID` | `DIAGNOS_WORKSPACE_ID` | deploy-time only — OpenBao policy bootstrap (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |
| `IMGEXAM_ACCOUNT_ID` | `DIAGNOS_ACCOUNT_ID` | deploy-time only — OpenBao policy bootstrap (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |

`OPENBAO_*` variables (`OPENBAO_ADDR`, `OPENBAO_TOKEN`, `OPENBAO_TOKEN_FILE`, `OPENBAO_MOUNT`,
`OPENBAO_PATH_PREFIX`, `OPENBAO_NAMESPACE`) were never `IMGEXAM_`-prefixed and are unchanged — OpenBao is a separate
product with its own naming. One of them changes behaviour, though: see the next section.

#### OpenBao auto-unseal: the default KV path prefix

The **default** value of the OpenBao KV path prefix (`DEFAULT_OPENBAO_PATH_PREFIX` in
`src/diagnos/transport/config.py`) changed from `"imgexam"` to `"diagnos"`. It is still overridden by the
`OPENBAO_PATH_PREFIX` environment variable, whose name did not change.

If you already run OpenBao auto-unseal against an `imgexam` deployment and upgrade in place without setting
`OPENBAO_PATH_PREFIX`, the SDK will start reading and writing under `diagnos/...` instead of `imgexam/...` — a path
that does not exist yet, so it will look like the saved session vanished. You have two options:

1. **Keep the old path.** Set `OPENBAO_PATH_PREFIX=imgexam` explicitly, and nothing else changes.
2. **Re-enroll.** Leave the new default (`diagnos`) in place and go through the enrollment/approval flow again; the
   SDK will save the new session under the new prefix on first success.

Either is safe — there is no silent data loss, only a saved session that needs to be found again or re-created.

#### What did NOT change, on purpose

Two categories of constant were deliberately **not** renamed, because they are persisted cryptographic wire
constants rather than product names:

- The `imgexam-*-v1` HKDF/AAD labels (`src/diagnos/crypto/hkdf.py`, `hybrid.py`, `keys.py`,
  `apps/sdk/native/src/hybrid/`) — for example `imgexam-sdk-hybrid-seal-v1`, `imgexam-patient-dek-v1`,
  `imgexam-drive-node-key-v1`.
- The OpenBao static seal key id `imgexam-static-v1` (`apps/api/deploy/k8s/autounseal/static/seal.hcl`).

Renaming any of these would make every piece of ciphertext already produced under the old label — or an existing
OpenBao static-seal install keyed to `imgexam-static-v1` — permanently unreadable. They are documented as frozen
next to their definitions and in [`CONTRIBUTING.md`](CONTRIBUTING.md); do not rename them in a fork or a patch.

### Find/replace checklist

Going through a checkout or a downstream fork, in roughly the order that will catch the most with the least risk of
a false match:

- [ ] Package names in your own `pyproject.toml`/`requirements`: `imgexam` → `diagnos[sdk]`, `imgexam-cli` →
      `diagnos[cli]`, `imgexam-api` → `diagnos[api]`.
- [ ] Python imports: `from imgexam` / `import imgexam` → `diagnos` (and `imgexam_cli`/`imgexam_api` →
      `diagnos.cli`/`diagnos.api`). Careful with a
      plain substring replace here — do it as import statements, not free text, or you will also touch the frozen
      `imgexam-*-v1` labels below.
- [ ] `Imgexam` → `Diagnos`, `ImgexamError` → `DiagnosError`, `ImgexamPermissionError` → `DiagnosPermissionError`.
- [ ] Every `IMGEXAM_*` environment variable in your shell profiles, `.env` files, CI secrets, Kubernetes
      `ConfigMap`/`Secret` manifests and Docker Compose files, per the table above.
- [ ] The `imgexam` CLI command → `diagnos` in scripts, cron jobs, systemd units, shell aliases.
- [ ] The `imgexam-api` Docker image reference → `ghcr.io/diagnos-tech/diagnos-api`, pinned by digest, in Compose
      files, Kubernetes manifests, CI.
- [ ] If you pin the vault URL: confirm it still points where you intend — the default changed, per above.
- [ ] If you use OpenBao auto-unseal: decide between the two options in the section above (`OPENBAO_PATH_PREFIX` or
      re-enroll) **before** deploying the rename, not after.
- [ ] **Leave untouched**: every `imgexam-*-v1` string in `crypto/`, `native/src/hybrid/`, `apps/sdk/tests/vectors/`,
      and `imgexam-static-v1` in `apps/api/deploy/k8s/autounseal/static/seal.hcl`.

### A one-liner to adapt

This covers the mechanical renames only — imports, the class/exception names, the CLI command, and the Docker image.
It deliberately does **not** touch environment variables (review those by hand against the table above, since some
live in secrets you don't want a blind rewrite near) or anything under `crypto/`, `native/src/`, `apps/sdk/tests/vectors/`
or `autounseal/` (the frozen `imgexam-*-v1` / `imgexam-static-v1` labels):

```sh
# Adjust the file list to your checkout; run on a clean git tree so you can review the diff.
grep -rlZ --include='*.py' --include='*.toml' --include='*.md' \
  -e 'imgexam' -e 'Imgexam' . \
  --exclude-dir={.git,crypto,native,vectors,autounseal} \
  | xargs -0 perl -pi -e '
      s/\bimgexam_(cli|api)\b/diagnos.$1/g;
      s/\bImgexam(PermissionError|Error)?\b/Diagnos$1/g;
      s/\bimgexam\b(?!-[a-z0-9-]*-v\d)/diagnos/g'
git diff   # review before committing — this is a blunt instrument
```

Adapt the `--exclude-dir` list and file globs to your own checkout's layout, and always review the diff: a blind
pass can still hit a string you did not expect; the `(?!…-vN)` guard keeps the frozen `imgexam-*-vN` labels intact.
