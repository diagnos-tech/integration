# Exemplo: Quickstart

[English](README.md) · **Português (Brasil)**

Lê a credencial de `DIAGNOS_CREDENTIAL`, faz o enrollment (o SDK imprime um link de aprovação e um código de 6 dígitos no `stderr`) e dá a primeira chamada: lista a primeira página de pacientes. Se só o `DIAGNOS_API_TOKEN` legado existir, avisa que está obsoleto (remoção em 2027-04-15) e segue.

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, uma credencial de conta de serviço em `DIAGNOS_CREDENTIAL` e alguém para aprovar o enrollment — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
workspace: ws_1
credential: ed25519 svc_00000000000000000000000000000000
groups: sg_oncology, sg_radiology
first call ok: 0 patient(s) on the first page
```

Código de saída: `0`; `2` erro de configuração, `3` enrollment negado ou expirado, ou credencial recusada.

Depois: [`03-patients`](../03-patients/README.pt-BR.md) para gravar dados, [`05-error-handling`](../05-error-handling/README.pt-BR.md) para falhas.
