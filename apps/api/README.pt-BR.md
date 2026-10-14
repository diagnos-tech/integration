# diagnos · API REST

[English](README.md) · **Português (Brasil)**

Uma fachada REST (FastAPI) sobre o SDK [`diagnos`](https://github.com/diagnos-tech/integration/tree/main/apps/sdk): um
processo, uma service account, uma sessão `Diagnos` viva na RAM, exposta a sistemas internos que preferem falar HTTP a
importar Python. Ela nunca acrescenta capacidade que o SDK já não tenha — toda rota é um invólucro fino sobre
`vault.patients`, `vault.exams` ou `vault.drives` — e TLS mútuo é a única autenticação que ela aceita. Ela é o
extra `api` do pacote único `diagnos` (`pip install "diagnos[api]"`, comando `diagnos-api`); o código dela mora em
`src/diagnos/api`.

O jeito suportado de rodá-la é a imagem assinada `ghcr.io/diagnos-tech/diagnos-api`, implantada pelo digest: o
`diagnos setup api` a baixa, verifica o digest baixado com cosign e imprime o run abaixo com esse digest. A
[Implantação](https://github.com/diagnos-tech/integration/blob/main/apps/api/deploy/README.pt-BR.md#a-imagem) tem os
detalhes, e `docker build --target api -t diagnos-api .` constrói a mesma imagem a partir de um checkout.

> [!NOTE]
> Vindo do `imgexam-api` ou do `diagnos-api`? Leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/main/MIGRATING.pt-BR.md) antes de atualizar.

## De relance

```sh
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
  --ulimit memlock=-1:-1 -p 8443:8443 -e DIAGNOS_API_TOKEN \
  -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
  -e DIAGNOS_API_TLS_CERT_FILE=/certs/tls.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/tls-key.pem \
  -v "$PWD/certs:/certs:ro" ghcr.io/diagnos-tech/diagnos-api@sha256:…

curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```

É também um processo Python comum — `diagnos-api` ou `python -m diagnos.api` — e, na sua própria máquina, o
`diagnos-api dev-certs` escreve uma CA descartável, um par de servidor para `localhost` e um par de cliente num passo
só; o [guia da API REST](https://github.com/diagnos-tech/integration/blob/main/docs/guides/api.pt-BR.md#experimente-na-sua-máquina)
mostra o caminho.

| Prefixo | O que serve |
|---|---|
| `/v1/patients` | registros de paciente cifrados — listar, criar, ler, atualizar, arquivar, lixeira, restaurar |
| `/v1/exams` | o mesmo para exames, cada um ligado a um paciente |
| `/v1/drives/{sg}` | arquivos e pastas de um security group — subir, listar, ler, baixar decifrado |
| `/v1/session` | a identidade deste processo e o certificado de quem chama; travar a sessão |
| `/healthz` | vivacidade, atrás do TLS mútuo como todo o resto |

Toda rota, parâmetro e schema está na referência gerada, e em `/docs` e `/openapi.json` num processo rodando — atrás
do certificado de cliente, como toda outra rota. Toda resposta não-2xx é `{"error": {"code", "message", "trace_id"}}`.

## Guias

| | |
|---|---|
| [Guia da API REST](https://github.com/diagnos-tech/integration/blob/main/docs/guides/api.pt-BR.md) | por que TLS mútuo, certificados, como rodar, como chamar toda rota com `curl` |
| [Referência da API](https://github.com/diagnos-tech/integration/blob/main/docs/reference/openapi.json) | o documento OpenAPI, gerado a partir do código |
| [Implantação](deploy/README.pt-BR.md) | ambiente, Kubernetes, Docker Compose, auto-unseal com OpenBao, travamento de memória |
| [Erros](https://github.com/diagnos-tech/integration/blob/main/docs/guides/errors.pt-BR.md#toda-exceção) | em qual status HTTP cada falha vira |
| [Modelo de segurança](https://github.com/diagnos-tech/integration/blob/main/docs/guides/security.pt-BR.md#a-fronteira-da-api-rest) | o que o processo da API guarda, e por que a CA de clientes é o controle de acesso |

Limites conhecidos e as questões ainda em aberto do lado do cofre:
[Compatibilidade com o cofre](https://github.com/diagnos-tech/integration/blob/main/docs/COMPATIBILITY.pt-BR.md).

## Desenvolvimento

```sh
make sync
uv run pytest apps/api/tests -q
uv run mypy src
make docs   # regera docs/reference/openapi.json depois de mudar uma rota
```

Os textos `summary` e `description` das rotas chegam ao site de documentação pelo documento OpenAPI gerado, então são
escritos para quem nunca abre o código: o que a rota faz, do que precisa, o que pode dar errado.
