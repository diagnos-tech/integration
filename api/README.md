# diagnos-api

🇺🇸 A REST facade (FastAPI) over the [`diagnos`](../sdk) SDK: one process,
one service account, one live `Diagnos` session in RAM, exposed to internal
systems that would rather speak HTTP than import Python. It never adds
capability the SDK does not already have — every route is a thin wrapper
over `vault.patients`/`vault.exams`/`vault.drives` (`CONVENTIONS.md`).

🇧🇷 Uma fachada REST (FastAPI) sobre o SDK [`diagnos`](../sdk): um processo,
uma service account, uma sessão `Diagnos` viva na RAM, exposta a sistemas
internos que preferem falar HTTP a importar Python. Nunca soma capacidade
que o SDK já não tenha — toda rota é um envoltório fino sobre
`vault.patients`/`vault.exams`/`vault.drives` (`CONVENTIONS.md`).

## Why mutual TLS, and only mutual TLS · Por que mTLS, e só mTLS

🇺🇸 There is no `Authorization` header, no API key, no session cookie. The
one thing this API accepts as identity is a client certificate signed by a
CA this deployment chose to trust — configured once, at startup, via
`DIAGNOS_API_MTLS_CA_FILE`. A bearer credential can be copied into a chat,
committed by accident, or replayed from a stolen log; a client certificate
cannot be reproduced from a leaked secret alone, because the caller has to
hold the private key the CA signed, and that key never travels over the
wire. This is also why a reverse proxy's `X-Forwarded-*` headers are never
treated as identity here: a proxy header is just a string anyone who
reached the proxy can set, while the TLS client certificate is the one
thing on the connection that got verified cryptographically, by uvicorn
itself, before any application code ran. A request without a valid client
certificate never completes the TLS handshake — it never becomes an HTTP
request at all, let alone reaches a route.

🇧🇷 Não existe header `Authorization`, API key, nem cookie de sessão. A
única coisa que esta API aceita como identidade é um certificado de cliente
assinado por uma CA que este deployment escolheu confiar — configurada uma
vez, na subida, via `DIAGNOS_API_MTLS_CA_FILE`. Uma credencial bearer pode
ser copiada num chat, commitada por acidente, ou reproduzida de um log
roubado; um certificado de cliente não pode ser reproduzido só a partir de
um segredo vazado, porque quem chama precisa ter a chave privada que a CA
assinou, e essa chave nunca viaja pela rede. É também por isso que headers
`X-Forwarded-*` de um proxy reverso nunca são tratados como identidade
aqui: um header de proxy é só uma string que qualquer um que alcançou o
proxy pode setar, enquanto o certificado de cliente TLS é a única coisa na
conexão que foi verificada criptograficamente, pelo próprio uvicorn, antes
de qualquer código de aplicação rodar. Uma requisição sem um certificado de
cliente válido nunca termina o handshake TLS — nunca vira uma requisição
HTTP, muito menos alcança uma rota.

## Generating a CA and certificates with `openssl` · Gerando uma CA e certificados com `openssl`

🇺🇸 For a real deployment, use whatever CA your organization already
operates. To try this locally, or to stand up a throwaway CA for a
non-production environment:

🇧🇷 Para um deployment de verdade, use a CA que sua organização já opera.
Para testar localmente, ou montar uma CA descartável para um ambiente que
não é produção:

```sh
# 🇺🇸 1. A CA that will sign both the server and every client certificate.
# 🇧🇷 1. Uma CA que vai assinar tanto o certificado do servidor quanto o de todo cliente.
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout clients-ca-key.pem -out clients-ca.pem \
  -subj "/CN=diagnos-api internal CA"

# 🇺🇸 2. The server's own certificate, for uvicorn to present to callers.
# 🇧🇷 2. O certificado do próprio servidor, para o uvicorn apresentar a quem chama.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout tls-key.pem -out server.csr \
  -subj "/CN=diagnos-api.internal"
openssl x509 -req -in server.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 825 -out tls.pem

# 🇺🇸 3. One client certificate per system allowed to call this API. The
#    CN below is what DIAGNOS_API_ALLOWED_CLIENT_CN can restrict against.
# 🇧🇷 3. Um certificado de cliente por sistema autorizado a chamar esta API.
#    O CN abaixo é o que DIAGNOS_API_ALLOWED_CLIENT_CN pode restringir.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout client-key.pem -out client.csr \
  -subj "/CN=billing-system"
openssl x509 -req -in client.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 365 -out client.pem
```

🇺🇸 Keep `clients-ca-key.pem` offline once you are done signing — this API
only ever needs the CA's public certificate (`clients-ca.pem`), never its
key, to verify callers.

🇧🇷 Guarde `clients-ca-key.pem` fora de linha depois de terminar de assinar
— esta API só precisa do certificado público da CA (`clients-ca.pem`),
nunca da chave dela, para verificar quem chama.

## Running it · Rodando

🇺🇸 Whichever way you run it, the environment table in
[`deploy/README.md`](deploy/README.md) is the full contract —
`DIAGNOS_API_TOKEN`, `DIAGNOS_API_MTLS_CA_FILE`,
`DIAGNOS_API_TLS_CERT_FILE`/`DIAGNOS_API_TLS_KEY_FILE` are required; host,
port, the CN allowlist and OpenBao auto-unseal are optional.

🇧🇷 De qualquer jeito que você rode, a tabela de ambiente em
[`deploy/README.md`](deploy/README.md) é o contrato completo —
`DIAGNOS_API_TOKEN`, `DIAGNOS_API_MTLS_CA_FILE`,
`DIAGNOS_API_TLS_CERT_FILE`/`DIAGNOS_API_TLS_KEY_FILE` são obrigatórias;
host, porta, a lista de CN permitidos e o auto-unseal do OpenBao são
opcionais.

```sh
# 🇺🇸/🇧🇷 python
export DIAGNOS_API_TOKEN="apikey-…"
export DIAGNOS_API_MTLS_CA_FILE=./clients-ca.pem
export DIAGNOS_API_TLS_CERT_FILE=./tls.pem
export DIAGNOS_API_TLS_KEY_FILE=./tls-key.pem
uv run --package diagnos-api diagnos-api
```

```sh
# 🇺🇸/🇧🇷 Docker — see api/Dockerfile
docker build -f api/Dockerfile -t diagnos-api .   # from apps/integration
docker run --rm -p 8443:8443 \
  -e DIAGNOS_API_TOKEN=apikey-… \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \
  -v $PWD/certs:/certs:ro diagnos-api
```

🇺🇸 For Kubernetes, see [`deploy/README.md`](deploy/README.md) — `deploy/k8s`
ships a Deployment, Service, ConfigMap and a Secret template.

🇧🇷 Para Kubernetes, veja [`deploy/README.md`](deploy/README.md) —
`deploy/k8s` traz um Deployment, Service, ConfigMap e um template de
Secret.

## OpenBao (auto-unseal) · OpenBao (auto-unseal)

🇺🇸 Without `OPENBAO_ADDR`/`OPENBAO_TOKEN`, every process restart re-enrolls:
it prints an approval link and a 6-digit code to the structured log
(`src/diagnos_api/logging.py`), and blocks until a workspace admin approves
it in the diagnos web app — fine for a one-off run, not for a pod that
restarts on its own schedule. Set both and the SDK saves its unlocked
session to OpenBao right after enrollment, restoring from there on every
later start with no human involved (`sdk/README.md`'s "Auto-unseal with
OpenBao" section has the full tradeoff). This API never touches OpenBao
directly — it is entirely the SDK's concern, configured through the same
environment variables `diagnos.Settings.from_env()` reads.

🇧🇷 Sem `OPENBAO_ADDR`/`OPENBAO_TOKEN`, todo reinício do processo refaz o
enrollment: imprime um link de aprovação e um código de 6 dígitos no log
estruturado (`src/diagnos_api/logging.py`), e bloqueia até um admin do
workspace aprovar no app web do diagnos — ok para uma rodada avulsa, não
para um pod que reinicia sozinho. Configure as duas e o SDK salva a sessão
desbloqueada no OpenBao logo após o enrollment, restaurando de lá em toda
subida seguinte sem humano envolvido (a seção "Auto-unseal com OpenBao" de
`sdk/README.md` tem o tradeoff completo). Esta API nunca toca o OpenBao
direto — é inteiramente responsabilidade do SDK, configurado pelas mesmas
variáveis de ambiente que `diagnos.Settings.from_env()` lê.

## Routes · Rotas

🇺🇸 Every route requires a client certificate; `{sg}` is a security group id.

🇧🇷 Toda rota exige certificado de cliente; `{sg}` é um id de security group.

| Method · Método | Path | 🇺🇸 · 🇧🇷 |
|---|---|---|
| `GET` | `/v1/patients` | List patient indexes · Lista índices de paciente |
| `POST` | `/v1/patients` | Create a patient · Cria um paciente |
| `GET` | `/v1/patients/{id}` | Get one patient (`?version_id=`) · Busca um paciente |
| `PUT` | `/v1/patients/{id}` | Update a patient · Atualiza um paciente |
| `POST` | `/v1/patients/{id}/archive` | Archive · Arquiva |
| `POST` | `/v1/patients/{id}/unarchive` | Unarchive · Desarquiva |
| `DELETE` | `/v1/patients/{id}` | Delete (soft) · Apaga (reversível) |
| `GET` | `/v1/exams` | List exam indexes · Lista índices de exame |
| `POST` | `/v1/exams` | Create an exam · Cria um exame |
| `GET` | `/v1/exams/{id}` | Get one exam (`?version_id=`) · Busca um exame |
| `PUT` | `/v1/exams/{id}` | Update an exam · Atualiza um exame |
| `POST` | `/v1/exams/{id}/archive` | Archive · Arquiva |
| `POST` | `/v1/exams/{id}/unarchive` | Unarchive · Desarquiva |
| `DELETE` | `/v1/exams/{id}` | Delete (soft) · Apaga (reversível) |
| `GET` | `/v1/drives/{sg}/nodes` | List drive nodes, names decrypted · Lista nós, nomes decifrados |
| `GET` | `/v1/drives/{sg}/nodes/{id}` | Get one node · Busca um nó |
| `POST` | `/v1/drives/{sg}/nodes` | Upload a file (multipart) · Sobe um arquivo (multipart) |
| `GET` | `/v1/drives/{sg}/nodes/{id}/content` | Download decrypted content · Baixa o conteúdo decifrado |
| `GET` | `/v1/session` | This process's identity and the caller's mTLS identity · Identidade deste processo e de quem chamou |
| `POST` | `/v1/session/lock` | Ends the SDK session · Encerra a sessão do SDK |
| `GET` | `/healthz` | Trivial 200 (still mTLS-gated) · 200 trivial (ainda travado por mTLS) |

🇺🇸 Full request/response schemas, generated from the code, are at
`/docs` (Swagger UI) and `/openapi.json` once the process is running —
reachable only with a valid client certificate, like everything else.

🇧🇷 Os esquemas completos de requisição/resposta, gerados do código, ficam
em `/docs` (Swagger UI) e `/openapi.json` com o processo rodando —
alcançáveis só com um certificado de cliente válido, como tudo mais.

## Error format · Formato de erro

🇺🇸 Every non-2xx response is `{"error": {"code": str, "message": str,
"trace_id": str | None}}`. `code`/`trace_id` come straight from the vault's
own error envelope when the failure originated there (`docs/PROTOCOL.md
§12`) — a `trace_id` is what a support ticket needs to find the event
server-side.

🇧🇷 Toda resposta não-2xx é `{"error": {"code": str, "message": str,
"trace_id": str | None}}`. `code`/`trace_id` vêm direto do envelope de erro
do próprio cofre quando a falha se originou lá (`docs/PROTOCOL.md §12`) — um
`trace_id` é o que um chamado de suporte precisa para achar o evento do
lado do servidor.

| HTTP | `diagnos` exception | 🇺🇸 · 🇧🇷 |
|---|---|---|
| 400 | `ValidationError` | The request itself is wrong · A requisição está errada |
| 401 | `AuthenticationError`, `SessionExpiredError` | Token/session/signature rejected · Token/sessão/assinatura recusados |
| 402 | `QuotaError` | No credit for this in the workspace · Sem crédito no workspace |
| 403 | `DiagnosPermissionError` | Not allowed here · Não permitido aqui |
| 404 | `NotFoundError` | Not found · Não encontrado |
| 409 | `ConflictError` | Pending version or replay · Versão pendente ou replay |
| 422 | (request body/query failed validation · corpo/query falhou validação) | |
| 429 | `RateLimitError` | Slow down · Devagar |
| 500 | `CryptoError` (no further detail · sem mais detalhe) | An envelope did not open · Um envelope não abriu |
| 502 | `VaultError` (any other code · qualquer outro código) | The vault itself failed · O próprio cofre falhou |

## Calling it with `curl` · Chamando com `curl`

```sh
curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```
