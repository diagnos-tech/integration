# Exemplo: Quickstart

[English](README.md) · **Português (Brasil)**

Acha o token de conta de serviço — `DIAGNOS_TOKEN`, ou onde o `diagnos login` o guardou — abre uma sessão com uma requisição assinada (sem aprovação, sem código) e dá a primeira chamada: lista a primeira página de pacientes. Com só o `DIAGNOS_API_TOKEN` legado definido, ainda roda, com aviso de depreciação (remoção em 2027-04-15).

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, e um token de conta de serviço em `DIAGNOS_TOKEN` (ou guardado pelo `diagnos login`) — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
workspace: ws_1
token: svc_00000000000000000000000000000000@ws_1.diagnos.health (from DIAGNOS_TOKEN)
groups: sg_oncology, sg_radiology
first call ok: 0 patient(s) on the first page
```

Código de saída: `0`; `2` erro de configuração (sem token, ou um colado errado), `3` o cofre recusou o token.

Depois: [`03-patients`](../03-patients/README.pt-BR.md) para gravar dados, [`05-error-handling`](../05-error-handling/README.pt-BR.md) para falhas.
