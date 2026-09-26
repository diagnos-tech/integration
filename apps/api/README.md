# diagnos-api

**English** · [Português (Brasil)](README.pt-BR.md)

A REST facade (FastAPI) over the [`diagnos`](https://github.com/diagnos-tech/integration/tree/develop/apps/sdk) SDK: one
process, one service account, one live `Diagnos` session in RAM, exposed to internal systems that would rather speak
HTTP than import Python. It never adds capability the SDK does not already have — every route is a thin wrapper over
`vault.patients`, `vault.exams` or `vault.drives` — and mutual TLS is the only authentication it accepts.

> [!NOTE]
> **Not on PyPI yet** — `diagnos-api` (and the `diagnos` SDK it depends on) has no published wheel. The Docker image
> built from `apps/api/Dockerfile` is the supported way to run it today: it builds the SDK, CLI and API from source
> inside the image, so it needs nothing from PyPI. Running it with `uv` from a source checkout works too.
>
> Coming from `imgexam-api`? Versions restart at `0.1.0` under the new name and image — read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.md) before upgrading.

## At a glance

```sh
docker build -f apps/api/Dockerfile -t diagnos-api .   # from the repository root
docker run --rm -p 8443:8443 --cap-add=IPC_LOCK \
  -e DIAGNOS_API_TOKEN=apikey-… \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/tls.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/tls-key.pem \
  -v "$PWD/certs:/certs:ro" diagnos-api

curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```

| Prefix | What it serves |
|---|---|
| `/v1/patients` | encrypted patient records — list, create, read, update, archive, trash, restore |
| `/v1/exams` | the same for exams, each linked to a patient |
| `/v1/drives/{sg}` | files and folders of one security group — upload, list, read, download decrypted |
| `/v1/session` | this process's identity and the caller's certificate; lock the session |
| `/healthz` | liveness, behind mutual TLS like everything else |

Every route, parameter and schema is in the generated reference, and at `/docs` and `/openapi.json` on a running
process. Every non-2xx response is `{"error": {"code", "message", "trace_id"}}`.

## Guides

| | |
|---|---|
| [REST API guide](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/api.md) | why mutual TLS, certificates, running it, calling every route with `curl` |
| [API reference](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/openapi.json) | the OpenAPI document, generated from the code |
| [Deploying](deploy/README.md) | environment, Kubernetes, Docker Compose, OpenBao auto-unseal, memory locking |
| [Errors](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.md#every-exception) | which HTTP status every failure becomes |
| [Security model](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/security.md#the-rest-apis-boundary) | what the API process holds, and why the client CA is the access control |

Known limits and the questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md).

## Development

```sh
make sync
uv run --package diagnos-api pytest apps/api/tests -q
uv run mypy apps/api/src
make docs   # regenerate docs/reference/openapi.json after changing a route
```

Route `summary` and `description` texts are written `🇺🇸 … 🇧🇷 …`: they reach the documentation site through the
generated OpenAPI document, and `make docs-check` refuses one without both languages.
