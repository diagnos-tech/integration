# diagnos-api

[English](README.md) · **Português (Brasil)**

Uma fachada REST (FastAPI) sobre o SDK [`diagnos`](https://github.com/diagnos-tech/integration/tree/develop/sdk): um
processo, uma service account, uma sessão `Diagnos` viva na RAM, exposta a sistemas internos que preferem falar HTTP
a importar Python. Nunca soma capacidade que o SDK já não tenha — toda rota é um envoltório fino sobre
`vault.patients`/`vault.exams`/`vault.drives`
([`CONTRIBUTING.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.pt-BR.md)).

> [!WARNING]
> As rotas `/v1/patients`, `/v1/exams` e `/v1/drives` envolvem camadas do SDK que ainda falam uma **revisão
> anterior** do protocolo do cofre e não são compatíveis com o cofre atual (`https://vault.diagnos.health`) — elas
> falham antes de gravar qualquer coisa. `/v1/session` e `/healthz` funcionam hoje. Veja
> [Compatibilidade com o cofre](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md)
> para o panorama completo e o plano para fechar essa lacuna.

> [!NOTE]
> **Ainda não está no PyPI** — `diagnos-api` (e o SDK `diagnos` do qual depende) não tem wheel publicado. A imagem
> Docker construída a partir de `api/Dockerfile` (abaixo) é o jeito suportado de rodar hoje: ela constrói o SDK, a
> CLI e a API a partir do fonte dentro da imagem, então não precisa de nada do PyPI para funcionar. Rodar com
> `python`/`uv` puro também funciona a partir de um checkout do fonte deste repositório (veja [Rodando](#rodando)
> abaixo), só não via `pip install` ainda.
>
> Vem do `imgexam-api`? As versões recomeçam em `0.1.0` sob o nome e a imagem novos — leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.pt-BR.md) antes de
> atualizar.

## Por que mTLS, e só mTLS

Não existe header `Authorization`, API key, nem cookie de sessão. A única coisa que esta API aceita como identidade é
um certificado de cliente assinado por uma CA que este deployment escolheu confiar — configurada uma vez, na subida,
via `DIAGNOS_API_MTLS_CA_FILE`. Uma credencial bearer pode ser copiada num chat, commitada por acidente, ou
reproduzida de um log roubado; um certificado de cliente não pode ser reproduzido só a partir de um segredo vazado,
porque quem chama precisa ter a chave privada que a CA assinou, e essa chave nunca viaja pela rede. É também por
isso que headers `X-Forwarded-*` de um proxy reverso nunca são tratados como identidade aqui: um header de proxy é
só uma string que qualquer um que alcançou o proxy pode setar, enquanto o certificado de cliente TLS é a única coisa
na conexão que foi verificada criptograficamente, pelo próprio uvicorn, antes de qualquer código de aplicação rodar.
Uma requisição sem um certificado de cliente válido nunca termina o handshake TLS — nunca vira uma requisição HTTP,
muito menos alcança uma rota.

## Gerando uma CA e certificados com `openssl`

Para um deployment de verdade, use a CA que sua organização já opera. Para testar localmente, ou montar uma CA
descartável para um ambiente que não é produção:

```sh
# 1. Uma CA que vai assinar tanto o certificado do servidor quanto o de todo cliente.
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout clients-ca-key.pem -out clients-ca.pem \
  -subj "/CN=diagnos-api internal CA"

# 2. O certificado do próprio servidor, para o uvicorn apresentar a quem chama.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout tls-key.pem -out server.csr \
  -subj "/CN=diagnos-api.internal"
openssl x509 -req -in server.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 825 -out tls.pem

# 3. Um certificado de cliente por sistema autorizado a chamar esta API. O
#    CN abaixo é o que DIAGNOS_API_ALLOWED_CLIENT_CN pode restringir.
openssl req -newkey rsa:4096 -sha256 -nodes -keyout client-key.pem -out client.csr \
  -subj "/CN=billing-system"
openssl x509 -req -in client.csr -CA clients-ca.pem -CAkey clients-ca-key.pem \
  -CAcreateserial -days 365 -out client.pem
```

Guarde `clients-ca-key.pem` fora de linha depois de terminar de assinar — esta API só precisa do certificado público
da CA (`clients-ca.pem`), nunca da chave dela, para verificar quem chama.

## Rodando

De qualquer jeito que você rode, a tabela de ambiente em [`deploy/README.pt-BR.md`](deploy/README.pt-BR.md) é o
contrato completo — `DIAGNOS_API_TOKEN`, `DIAGNOS_API_MTLS_CA_FILE`,
`DIAGNOS_API_TLS_CERT_FILE`/`DIAGNOS_API_TLS_KEY_FILE` são obrigatórias; host, porta, a lista de CN permitidos e o
auto-unseal do OpenBao são opcionais.

```sh
# python
export DIAGNOS_API_TOKEN="apikey-…"
export DIAGNOS_API_MTLS_CA_FILE=./clients-ca.pem
export DIAGNOS_API_TLS_CERT_FILE=./tls.pem
export DIAGNOS_API_TLS_KEY_FILE=./tls-key.pem
uv run --package diagnos-api diagnos-api
```

```sh
# Docker — veja api/Dockerfile
docker build -f api/Dockerfile -t diagnos-api .   # a partir da raiz do repositório
docker run --rm -p 8443:8443 --cap-add=IPC_LOCK \
  -e DIAGNOS_API_TOKEN=apikey-… \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \
  -v $PWD/certs:/certs:ro diagnos-api
```

`--cap-add=IPC_LOCK` é o que permite o SDK travar as chaves na RAM além do padrão de 64 KiB; sem isso o container
ainda sobe e roda em modo best-effort — veja a seção "Travamento de memória" do
[`deploy/README.pt-BR.md`](deploy/README.pt-BR.md) para a história completa em três partes (capability,
`RLIMIT_MEMLOCK`, `DIAGNOS_MEMORY_LOCK`).

Para Kubernetes, veja [`deploy/README.pt-BR.md`](deploy/README.pt-BR.md) — `deploy/k8s` traz um Deployment, Service,
ConfigMap e um template de Secret.

## OpenBao (auto-unseal)

Sem `OPENBAO_ADDR`/`OPENBAO_TOKEN`, todo reinício do processo refaz o enrollment: imprime um link de aprovação e um
código de 6 dígitos no log estruturado (`src/diagnos_api/logging.py`), e bloqueia até um admin do workspace aprovar
no app web do diagnos — ok para uma rodada avulsa, não para um pod que reinicia sozinho. Configure as duas e o SDK
salva a sessão desbloqueada no OpenBao logo após o enrollment, restaurando de lá em toda subida seguinte sem humano
envolvido (a seção
[Auto-unseal com OpenBao](https://github.com/diagnos-tech/integration/blob/develop/sdk/README.pt-BR.md#auto-unseal-com-openbao)
do SDK tem o tradeoff completo). Esta API nunca toca o OpenBao direto — é inteiramente responsabilidade do SDK,
configurado pelas mesmas variáveis de ambiente que `diagnos.Settings.from_env()` lê.

## Rotas

Toda rota exige certificado de cliente; `{sg}` é um id de security group.

| Método | Caminho | O que faz | Situação |
|---|---|---|---|
| `GET` | `/v1/patients` | Lista índices de paciente | ⚠️ veja o aviso |
| `POST` | `/v1/patients` | Cria um paciente | ⚠️ veja o aviso |
| `GET` | `/v1/patients/{id}` | Busca um paciente (`?version_id=`) | ⚠️ veja o aviso |
| `PUT` | `/v1/patients/{id}` | Atualiza um paciente | ⚠️ veja o aviso |
| `POST` | `/v1/patients/{id}/archive` | Arquiva | ⚠️ veja o aviso |
| `POST` | `/v1/patients/{id}/unarchive` | Desarquiva | ⚠️ veja o aviso |
| `DELETE` | `/v1/patients/{id}` | Apaga (reversível) | ⚠️ veja o aviso |
| `GET` | `/v1/exams` | Lista índices de exame | ⚠️ veja o aviso |
| `POST` | `/v1/exams` | Cria um exame | ⚠️ veja o aviso |
| `GET` | `/v1/exams/{id}` | Busca um exame (`?version_id=`) | ⚠️ veja o aviso |
| `PUT` | `/v1/exams/{id}` | Atualiza um exame | ⚠️ veja o aviso |
| `POST` | `/v1/exams/{id}/archive` | Arquiva | ⚠️ veja o aviso |
| `POST` | `/v1/exams/{id}/unarchive` | Desarquiva | ⚠️ veja o aviso |
| `DELETE` | `/v1/exams/{id}` | Apaga (reversível) | ⚠️ veja o aviso |
| `GET` | `/v1/drives/{sg}/nodes` | Lista nós, nomes decifrados | ⚠️ veja o aviso |
| `GET` | `/v1/drives/{sg}/nodes/{id}` | Busca um nó | ⚠️ veja o aviso |
| `POST` | `/v1/drives/{sg}/nodes` | Sobe um arquivo (multipart) | ⚠️ veja o aviso |
| `GET` | `/v1/drives/{sg}/nodes/{id}/content` | Baixa o conteúdo decifrado | ⚠️ veja o aviso |
| `GET` | `/v1/session` | Identidade deste processo e a identidade mTLS de quem chamou | ✅ funciona hoje |
| `POST` | `/v1/session/lock` | Encerra a sessão do SDK | ✅ funciona hoje |
| `GET` | `/healthz` | 200 trivial (ainda travado por mTLS) | ✅ funciona hoje |

Linhas marcadas com ⚠️ falham contra o cofre de produção de hoje — veja o aviso no topo deste documento.

Os esquemas completos de requisição/resposta, gerados do código, ficam em `/docs` (Swagger UI) e `/openapi.json` com
o processo rodando — alcançáveis só com um certificado de cliente válido, como tudo mais.

## Formato de erro

Toda resposta não-2xx é `{"error": {"code": str, "message": str, "trace_id": str | None}}`. `code`/`trace_id` vêm
direto do envelope de erro do próprio cofre quando a falha se originou lá
([`docs/PROTOCOL.md` §12](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md)) — um
`trace_id` é o que um chamado de suporte precisa para achar o evento do lado do servidor.

| HTTP | Exceção `diagnos` | Significado |
|---|---|---|
| 400 | `ValidationError` | A requisição está errada |
| 401 | `AuthenticationError`, `SessionExpiredError` | Token/sessão/assinatura recusados |
| 402 | `QuotaError` | Sem crédito no workspace |
| 403 | `DiagnosPermissionError` | Não permitido aqui |
| 404 | `NotFoundError` | Não encontrado |
| 409 | `ConflictError` | Versão pendente ou replay |
| 422 | — | Corpo/query da requisição falhou validação |
| 429 | `RateLimitError` | Devagar |
| 500 | `CryptoError` | Um envelope não abriu (sem mais detalhe) |
| 502 | `VaultError` | O próprio cofre falhou (qualquer outro código) |

## Chamando com `curl`

```sh
curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```
