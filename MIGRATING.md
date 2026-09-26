# Migrating from imgexam

**English** · [Português (Brasil)](MIGRATING.pt-BR.md)

This project was renamed from `imgexam` to `diagnos`. The packages were never published to PyPI under either name —
if you only ever installed `diagnos`, `diagnos-cli` or `diagnos-api`, there is nothing here for you. This guide is
for anyone who ran an internal or from-source checkout of the former `imgexam` monorepo (packages, a vendored copy,
or a deployment built from source) and is moving that checkout to this repository.

`0.1.0` is the first version of `diagnos`, `diagnos-cli` and `diagnos-api` ever published as such — see
[`CHANGELOG.md`](CHANGELOG.md). All three restart their versioning at `0.1.0` regardless of what `imgexam`'s
internal version numbers were.

## What changed

### Packages, modules, classes, exceptions

| Before (`imgexam`) | After (`diagnos`) |
|---|---|
| package `imgexam` | package `diagnos` |
| package `imgexam-cli` | package `diagnos-cli` |
| package `imgexam-api` | package `diagnos-api` |
| import `imgexam` | import `diagnos` |
| import `imgexam_cli` | import `diagnos_cli` |
| import `imgexam_api` | import `diagnos_api` |
| class `Imgexam` | class `Diagnos` |
| exception `ImgexamError` | exception `DiagnosError` |
| exception `ImgexamPermissionError` | exception `DiagnosPermissionError` |

```python no-run
# before
from imgexam import Imgexam, ImgexamError

# after
from diagnos import Diagnos, DiagnosError
```

### CLI command and Docker image

| Before | After |
|---|---|
| `imgexam` (command) | `diagnos` (command) |
| `imgexam-api` (Docker image) | `diagnos-api` (Docker image) |

### Default vault URL

The default vault URL changed from the previous internal address to `https://vault.diagnos.health`. If you set
`DIAGNOS_VAULT_URL` (see below) explicitly, this does not affect you.

### Environment variables

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
| `IMGEXAM_API_MTLS_CA_FILE` | `DIAGNOS_API_MTLS_CA_FILE` | API (`diagnos_api/settings.py`), deploy manifests |
| `IMGEXAM_API_TLS_CERT_FILE` | `DIAGNOS_API_TLS_CERT_FILE` | API (`diagnos_api/settings.py`), deploy manifests |
| `IMGEXAM_API_TLS_KEY_FILE` | `DIAGNOS_API_TLS_KEY_FILE` | API (`diagnos_api/settings.py`), deploy manifests |
| `IMGEXAM_API_HOST` | `DIAGNOS_API_HOST` | API (`diagnos_api/settings.py`) |
| `IMGEXAM_API_PORT` | `DIAGNOS_API_PORT` | API (`diagnos_api/settings.py`), deploy manifests |
| `IMGEXAM_API_ALLOWED_CLIENT_CN` | `DIAGNOS_API_ALLOWED_CLIENT_CN` | API (`diagnos_api/settings.py`) |
| `IMGEXAM_WORKSPACE_ID` | `DIAGNOS_WORKSPACE_ID` | deploy-time only — OpenBao policy bootstrap (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |
| `IMGEXAM_ACCOUNT_ID` | `DIAGNOS_ACCOUNT_ID` | deploy-time only — OpenBao policy bootstrap (`apps/api/deploy/k8s/openbao/`, `apps/api/deploy/compose/openbao/`) |

`OPENBAO_*` variables (`OPENBAO_ADDR`, `OPENBAO_TOKEN`, `OPENBAO_TOKEN_FILE`, `OPENBAO_MOUNT`,
`OPENBAO_PATH_PREFIX`, `OPENBAO_NAMESPACE`) were never `IMGEXAM_`-prefixed and are unchanged — OpenBao is a separate
product with its own naming. One of them changes behaviour, though: see the next section.

### OpenBao auto-unseal: the default KV path prefix

The **default** value of the OpenBao KV path prefix (`DEFAULT_OPENBAO_PATH_PREFIX` in
`apps/sdk/src/diagnos/transport/config.py`) changed from `"imgexam"` to `"diagnos"`. It is still overridden by the
`OPENBAO_PATH_PREFIX` environment variable, whose name did not change.

If you already run OpenBao auto-unseal against an `imgexam` deployment and upgrade in place without setting
`OPENBAO_PATH_PREFIX`, the SDK will start reading and writing under `diagnos/...` instead of `imgexam/...` — a path
that does not exist yet, so it will look like the saved session vanished. You have two options:

1. **Keep the old path.** Set `OPENBAO_PATH_PREFIX=imgexam` explicitly, and nothing else changes.
2. **Re-enroll.** Leave the new default (`diagnos`) in place and go through the enrollment/approval flow again; the
   SDK will save the new session under the new prefix on first success.

Either is safe — there is no silent data loss, only a saved session that needs to be found again or re-created.

### What did NOT change, on purpose

Two categories of constant were deliberately **not** renamed, because they are persisted cryptographic wire
constants rather than product names:

- The `imgexam-*-v1` HKDF/AAD labels (`apps/sdk/src/diagnos/crypto/hkdf.py`, `hybrid.py`, `keys.py`,
  `apps/sdk/native/src/hybrid.rs`) — for example `imgexam-sdk-hybrid-seal-v1`, `imgexam-patient-dek-v1`,
  `imgexam-drive-node-key-v1`.
- The OpenBao static seal key id `imgexam-static-v1` (`apps/api/deploy/k8s/autounseal/static/seal.hcl`).

Renaming any of these would make every piece of ciphertext already produced under the old label — or an existing
OpenBao static-seal install keyed to `imgexam-static-v1` — permanently unreadable. They are documented as frozen
next to their definitions and in [`CONTRIBUTING.md`](CONTRIBUTING.md); do not rename them in a fork or a patch.

## Find/replace checklist

Going through a checkout or a downstream fork, in roughly the order that will catch the most with the least risk of
a false match:

- [ ] Package names in your own `pyproject.toml`/`requirements`: `imgexam` → `diagnos`, `imgexam-cli` →
      `diagnos-cli`, `imgexam-api` → `diagnos-api`.
- [ ] Python imports: `from imgexam` / `import imgexam` → `diagnos` (and the `_cli`/`_api` variants). Careful with a
      plain substring replace here — do it as import statements, not free text, or you will also touch the frozen
      `imgexam-*-v1` labels below.
- [ ] `Imgexam` → `Diagnos`, `ImgexamError` → `DiagnosError`, `ImgexamPermissionError` → `DiagnosPermissionError`.
- [ ] Every `IMGEXAM_*` environment variable in your shell profiles, `.env` files, CI secrets, Kubernetes
      `ConfigMap`/`Secret` manifests and Docker Compose files, per the table above.
- [ ] The `imgexam` CLI command → `diagnos` in scripts, cron jobs, systemd units, shell aliases.
- [ ] The `imgexam-api` Docker image reference → `diagnos-api` in Compose files, Kubernetes manifests, CI.
- [ ] If you pin the vault URL: confirm it still points where you intend — the default changed, per above.
- [ ] If you use OpenBao auto-unseal: decide between the two options in the section above (`OPENBAO_PATH_PREFIX` or
      re-enroll) **before** deploying the rename, not after.
- [ ] **Leave untouched**: every `imgexam-*-v1` string in `crypto/`, `native/src/hybrid.rs`, `apps/sdk/tests/vectors/`,
      and `imgexam-static-v1` in `apps/api/deploy/k8s/autounseal/static/seal.hcl`.

## A one-liner to adapt

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
      s/\bimgexam_(cli|api)\b/diagnos_$1/g;
      s/\bImgexam(PermissionError|Error)?\b/Diagnos$1/g;
      s/\bimgexam\b(?!-[a-z0-9-]*-v\d)/diagnos/g'
git diff   # review before committing — this is a blunt instrument
```

Adapt the `--exclude-dir` list and file globs to your own checkout's layout, and always review the diff: a blind
pass can still hit a string you did not expect; the `(?!…-vN)` guard keeps the frozen `imgexam-*-vN` labels intact.
