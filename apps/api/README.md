# diagnos · REST API

**English** · [Português (Brasil)](README.pt-BR.md)

A REST facade (FastAPI) over the [`diagnos`](https://github.com/diagnos-tech/integration/tree/main/apps/sdk) SDK: one
process, one service account, one live `Diagnos` session in RAM, exposed to internal systems that would rather speak
HTTP than import Python. It never adds capability the SDK does not already have — every route is a thin wrapper over
`vault.patients`, `vault.exams` or `vault.drives` — and mutual TLS is the only authentication it accepts. It is the
`api` extra of the one `diagnos` package (`pip install "diagnos[api]"`, command `diagnos-api`); its code lives in
`src/diagnos/api`.

The supported way to run it is the signed image `ghcr.io/diagnos-tech/diagnos-api`, deployed by digest:
`diagnos setup api` pulls it, verifies the pulled digest with cosign and prints the run below with that digest.
[Deploying](https://github.com/diagnos-tech/integration/blob/main/apps/api/deploy/README.md#the-image) has the
details, and `docker build --target api -t diagnos-api .` builds the same image from a checkout.

> [!NOTE]
> Coming from `imgexam-api` or `diagnos-api`? Read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/main/MIGRATING.md) before upgrading.

## At a glance

```sh
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
  --ulimit memlock=-1:-1 -p 8443:8443 -e DIAGNOS_API_TOKEN \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/tls.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/tls-key.pem \
  -v "$PWD/certs:/certs:ro" ghcr.io/diagnos-tech/diagnos-api@sha256:…

curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```

It is an ordinary Python process too — `diagnos-api` or `python -m diagnos.api` — and on your own machine
`diagnos-api dev-certs` writes a throwaway CA, a `localhost` server pair and a client pair in one step; the
[REST API guide](https://github.com/diagnos-tech/integration/blob/main/docs/guides/api.md#try-it-on-your-machine)
walks through it.

| Prefix | What it serves |
|---|---|
| `/v1/patients` | encrypted patient records — list, create, read, update, archive, trash, restore |
| `/v1/exams` | the same for exams, each linked to a patient |
| `/v1/drives/{sg}` | files and folders of one security group — upload, list, read, download decrypted |
| `/v1/session` | this process's identity and the caller's certificate; lock the session |
| `/healthz` | liveness, behind mutual TLS like everything else |

Every route, parameter and schema is in the generated reference, and at `/docs` and `/openapi.json` on a running
process — behind the client certificate, like every other route. Every non-2xx response is
`{"error": {"code", "message", "trace_id"}}`.

## Guides

| | |
|---|---|
| [REST API guide](https://github.com/diagnos-tech/integration/blob/main/docs/guides/api.md) | why mutual TLS, certificates, running it, calling every route with `curl` |
| [API reference](https://github.com/diagnos-tech/integration/blob/main/docs/reference/openapi.json) | the OpenAPI document, generated from the code |
| [Deploying](deploy/README.md) | environment, Kubernetes, Docker Compose, OpenBao auto-unseal, memory locking |
| [Errors](https://github.com/diagnos-tech/integration/blob/main/docs/guides/errors.md#every-exception) | which HTTP status every failure becomes |
| [Security model](https://github.com/diagnos-tech/integration/blob/main/docs/guides/security.md#the-rest-apis-boundary) | what the API process holds, and why the client CA is the access control |

Known limits and the questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/main/docs/COMPATIBILITY.md).

## Development

```sh
make sync
uv run pytest apps/api/tests -q
uv run mypy src
make docs   # regenerate docs/reference/openapi.json after changing a route
```

Route `summary` and `description` texts are written `🇺🇸 … 🇧🇷 …`: they reach the documentation site through the
generated OpenAPI document, and `make docs-check` refuses one without both languages.
