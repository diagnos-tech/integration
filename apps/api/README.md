# diagnos-api

**English** · [Português (Brasil)](README.pt-BR.md)

A REST facade (FastAPI) over the [`diagnos`](https://github.com/diagnos-tech/integration/tree/develop/apps/sdk) SDK: one
process, one service account, one live `Diagnos` session in RAM, exposed to internal systems that would rather speak
HTTP than import Python. It never adds capability the SDK does not already have — every route is a thin wrapper over
`vault.patients`/`vault.exams`/`vault.drives`
([`CONTRIBUTING.md`](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.md)).

> [!NOTE]
> **Not on PyPI yet** — `diagnos-api` (and the `diagnos` SDK it depends on) has no published wheel. The Docker image
> built from `apps/api/Dockerfile` (below) is the supported way to run it today: it builds the SDK, CLI and API from
> source inside the image, so it needs nothing from PyPI to work. Running it with plain `python`/`uv` also works
> from a source checkout of this repository (see [Running it](#running-it) below), just not yet via `pip install`.
>
> Coming from `imgexam-api`? Versions restart at `0.1.0` under the new name and image — read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.md) before upgrading.

## Why mutual TLS, and only mutual TLS

There is no `Authorization` header, no API key, no session cookie. The one thing this API accepts as identity is a
client certificate signed by a CA this deployment chose to trust — configured once, at startup, via
`DIAGNOS_API_MTLS_CA_FILE`. A bearer credential can be copied into a chat, committed by accident, or replayed from a
stolen log; a client certificate cannot be reproduced from a leaked secret alone, because the caller has to hold the
private key the CA signed, and that key never travels over the wire. This is also why a reverse proxy's
`X-Forwarded-*` headers are never treated as identity here: a proxy header is just a string anyone who reached the
proxy can set, while the TLS client certificate is the one thing on the connection that got verified
cryptographically, by uvicorn itself, before any application code ran. A request without a valid client certificate
never completes the TLS handshake — it never becomes an HTTP request at all, let alone reaches a route.

## Generating a CA and certificates with `openssl`

For a real deployment, use whatever CA your organization already operates. To try this locally, or to stand up a
throwaway CA for a non-production environment:

```sh
# 1. A CA that will sign both the server and every client certificate.
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout clients-ca-key.pem -out clients-ca.pem \
  -subj "/CN=diagnos-api internal CA"

# 2. The server's own certificate, for uvicorn to present to callers.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout tls-key.pem -out server.csr \
  -subj "/CN=diagnos-api.internal"
openssl x509 -req -in server.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 825 -out tls.pem

# 3. One client certificate per system allowed to call this API. The
#    CN below is what DIAGNOS_API_ALLOWED_CLIENT_CN can restrict against.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout client-key.pem -out client.csr \
  -subj "/CN=billing-system"
openssl x509 -req -in client.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 365 -out client.pem
```

Keep `clients-ca-key.pem` offline once you are done signing — this API only ever needs the CA's public certificate
(`clients-ca.pem`), never its key, to verify callers.

## Running it

Whichever way you run it, the environment table in [`deploy/README.md`](deploy/README.md) is the full contract —
`DIAGNOS_API_TOKEN`, `DIAGNOS_API_MTLS_CA_FILE`, `DIAGNOS_API_TLS_CERT_FILE`/`DIAGNOS_API_TLS_KEY_FILE` are required;
host, port, the CN allowlist and OpenBao auto-unseal are optional.

```sh
# python
export DIAGNOS_API_TOKEN="apikey-…"
export DIAGNOS_API_MTLS_CA_FILE=./clients-ca.pem
export DIAGNOS_API_TLS_CERT_FILE=./tls.pem
export DIAGNOS_API_TLS_KEY_FILE=./tls-key.pem
uv run --package diagnos-api diagnos-api
```

```sh
# Docker — see apps/api/Dockerfile
docker build -f apps/api/Dockerfile -t diagnos-api .   # from the repository root
docker run --rm -p 8443:8443 --cap-add=IPC_LOCK \
  -e DIAGNOS_API_TOKEN=apikey-… \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \
  -v $PWD/certs:/certs:ro diagnos-api
```

`--cap-add=IPC_LOCK` is what lets the SDK lock its keys in RAM past the 64 KiB default; without it the container
still starts and runs in best-effort mode — see the "Memory locking" section of [`deploy/README.md`](deploy/README.md)
for the full three-part story (capability, `RLIMIT_MEMLOCK`, `DIAGNOS_MEMORY_LOCK`).

For Kubernetes, see [`deploy/README.md`](deploy/README.md) — `deploy/k8s` ships a Deployment, Service, ConfigMap and
a Secret template.

## OpenBao (auto-unseal)

Without `OPENBAO_ADDR`/`OPENBAO_TOKEN`, every process restart re-enrolls: it prints an approval link and a 6-digit
code to the structured log (`src/diagnos_api/logging.py`), and blocks until a workspace admin approves it in the
diagnos web app — fine for a one-off run, not for a pod that restarts on its own schedule. Set both and the SDK
saves its unlocked session to OpenBao right after enrollment, restoring from there on every later start with no
human involved (the SDK's
[Auto-unseal with OpenBao](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md#auto-unseal-with-openbao)
section has the full tradeoff). This API never touches OpenBao directly — it is entirely the SDK's concern,
configured through the same environment variables `diagnos.Settings.from_env()` reads.

## Routes

Every route requires a client certificate; `{sg}` is a security group id.

| Method | Path | What it does | Status |
|---|---|---|---|
| `GET` | `/v1/patients` | List patients (`?summary=true` adds decrypted names and tags) | ✅ works today |
| `POST` | `/v1/patients` | Create a patient (`record`, `security_group`, `tags`, `specialist_ids`) | ✅ works today |
| `GET` | `/v1/patients/{id}` | Get one patient (`?version_id=`, `?include_draft=false`) | ✅ works today |
| `PUT` | `/v1/patients/{id}` | New complete version (`record`, `tags`, `expected_latest_version_id`) | ✅ works today |
| `POST` | `/v1/patients/{id}/archive` | Archive (no new version) | ✅ works today |
| `POST` | `/v1/patients/{id}/unarchive` | Unarchive | ✅ works today |
| `DELETE` | `/v1/patients/{id}` | Move to the trash (soft) | ✅ works today |
| `POST` | `/v1/patients/{id}/restore` | Take out of the trash | ✅ works today |
| `GET` | `/v1/exams` | List exams (`?summary=true` adds title, modality and date) | ✅ works today |
| `POST` | `/v1/exams` | Create an exam (`record`, `patient_id`, `security_group`) | ✅ works today |
| `GET` | `/v1/exams/{id}` | Get one exam (`?version_id=`, `?include_draft=false`) | ✅ works today |
| `PUT` | `/v1/exams/{id}` | New complete version (`record`, `expected_latest_version_id`) | ✅ works today |
| `POST` | `/v1/exams/{id}/archive` | Archive (no new version) | ✅ works today |
| `POST` | `/v1/exams/{id}/unarchive` | Unarchive | ✅ works today |
| `DELETE` | `/v1/exams/{id}` | Move to the trash (soft) | ✅ works today |
| `POST` | `/v1/exams/{id}/restore` | Take out of the trash | ✅ works today |
| `GET` | `/v1/drives/{sg}/nodes` | List files and folders, names decrypted (`?parent_id=`, `?exam_id=`, `?include_pending=`, `?limit=` 1–200, `?cursor=`) | ✅ works today |
| `GET` | `/v1/drives/{sg}/nodes/{id}` | One file's metadata and decrypted name | ✅ works today |
| `POST` | `/v1/drives/{sg}/nodes` | Upload a file (`multipart/form-data`: `file`, optional `exam_id`, `parent_id`, `mime_type`) | ✅ works today |
| `POST` | `/v1/drives/{sg}/folders` | Create a folder (`name`, `parent_id`) → `{node_id}` | ✅ works today |
| `GET` | `/v1/drives/{sg}/nodes/{id}/content` | Stream the decrypted content, named by its last path segment | ✅ works today |
| `GET` | `/v1/session` | This process's identity and the caller's mTLS identity | ✅ works today |
| `POST` | `/v1/session/lock` | Ends the SDK session | ✅ works today |
| `GET` | `/healthz` | Trivial 200 (still mTLS-gated) | ✅ works today |

A node read under the wrong `{sg}` answers `404`, exactly like one that does not exist. Known limits and the
questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md).

Full request/response schemas, generated from the code, are at `/docs` (Swagger UI) and `/openapi.json` once the
process is running — reachable only with a valid client certificate, like everything else.

## Error format

Every non-2xx response is `{"error": {"code": str, "message": str, "trace_id": str | None}}`. `code`/`trace_id` come
straight from the vault's own error envelope when the failure originated there
([`docs/PROTOCOL.md` §12](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.md)) — a `trace_id`
is what a support ticket needs to find the event server-side.

| HTTP | `diagnos` exception | Meaning |
|---|---|---|
| 400 | `ValidationError` | The request itself is wrong |
| 401 | `AuthenticationError`, `SessionExpiredError` | Token/session/signature rejected |
| 402 | `QuotaError` | No credit for this in the workspace |
| 403 | `DiagnosPermissionError` | Not allowed here |
| 403 | `GroupKeyUnavailable` (`code: group_key_unavailable`) | This process was never handed the key of the data's security group — an admin approves an enrollment covering it |
| 404 | `NotFoundError` | Not found |
| 409 | `ConflictError` | Pending or newer version, replay, or an upload that never reached storage |
| 422 | — | Request body/query failed validation |
| 429 | `RateLimitError` | Slow down |
| 500 | `CryptoError` | An envelope did not open (no further detail) |
| 502 | `VaultError` | The vault itself failed (any other code) |
| 502 | `ProtocolError` (`code: protocol_error`) | The vault answered something the protocol does not allow |

## Calling it with `curl`

```sh
curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```
