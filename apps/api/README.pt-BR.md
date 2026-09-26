# diagnos-api

[English](README.md) · **Português (Brasil)**

Uma fachada REST (FastAPI) sobre o SDK [`diagnos`](https://github.com/diagnos-tech/integration/tree/develop/apps/sdk): um
processo, uma service account, uma sessão `Diagnos` viva na RAM, exposta a sistemas internos que preferem falar HTTP a
importar Python. Ela nunca acrescenta capacidade que o SDK já não tenha — toda rota é um invólucro fino sobre
`vault.patients`, `vault.exams` ou `vault.drives` — e TLS mútuo é a única autenticação que ela aceita.

> [!NOTE]
> **Ainda não está no PyPI** — o `diagnos-api` (e o SDK `diagnos` de que depende) não tem wheel publicado. A imagem
> Docker construída a partir de `apps/api/Dockerfile` é a forma suportada de rodá-lo hoje: ela constrói o SDK, a CLI e
> a API do código-fonte dentro da imagem, então não precisa de nada do PyPI. Rodar com `uv` a partir de um checkout
> também funciona.
>
> Vindo do `imgexam-api`? As versões recomeçam em `0.1.0` sob o nome e a imagem novos — leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.pt-BR.md) antes de atualizar.

## De relance

```sh
docker build -f apps/api/Dockerfile -t diagnos-api .   # da raiz do repositório
docker run --rm -p 8443:8443 --cap-add=IPC_LOCK \
  -e DIAGNOS_API_TOKEN=apikey-… \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/tls.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/tls-key.pem \
  -v "$PWD/certs:/certs:ro" diagnos-api

curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```

| Prefixo | O que serve |
|---|---|
| `/v1/patients` | registros de paciente cifrados — listar, criar, ler, atualizar, arquivar, lixeira, restaurar |
| `/v1/exams` | o mesmo para exames, cada um ligado a um paciente |
| `/v1/drives/{sg}` | arquivos e pastas de um security group — subir, listar, ler, baixar decifrado |
| `/v1/session` | a identidade deste processo e o certificado de quem chama; travar a sessão |
| `/healthz` | vivacidade, atrás do TLS mútuo como todo o resto |

Toda rota, parâmetro e schema está na referência gerada, e em `/docs` e `/openapi.json` num processo rodando. Toda
resposta não-2xx é `{"error": {"code", "message", "trace_id"}}`.

## Guias

| | |
|---|---|
| [Guia da API REST](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/api.pt-BR.md) | por que TLS mútuo, certificados, como rodar, como chamar toda rota com `curl` |
| [Referência da API](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/openapi.json) | o documento OpenAPI, gerado a partir do código |
| [Implantação](deploy/README.pt-BR.md) | ambiente, Kubernetes, Docker Compose, auto-unseal com OpenBao, travamento de memória |
| [Erros](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.pt-BR.md#toda-exceção) | em qual status HTTP cada falha vira |
| [Modelo de segurança](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/security.pt-BR.md#a-fronteira-da-api-rest) | o que o processo da API guarda, e por que a CA de clientes é o controle de acesso |

Limites conhecidos e as questões ainda em aberto do lado do cofre:
[Compatibilidade com o cofre](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md).

## Desenvolvimento

```sh
make sync
uv run --package diagnos-api pytest apps/api/tests -q
uv run mypy apps/api/src
make docs   # regera docs/reference/openapi.json depois de mudar uma rota
```

Os textos `summary` e `description` das rotas são escritos `🇺🇸 … 🇧🇷 …`: chegam ao site de documentação pelo
documento OpenAPI gerado, e o `make docs-check` recusa um sem as duas línguas.
