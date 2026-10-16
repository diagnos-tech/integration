# Exemplo: Trancar a sessão

[English](README.md) · **Português (Brasil)**

Desbloqueia, faz algum trabalho e encerra a sessão de propósito num `finally`: `lock()` a encerra no cofre (best effort) e sempre apaga as chaves deste processo. Sair de um bloco `with` não faz isso — só fecha os clients HTTP, para um worker que reinicia poder retomar a sessão.

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, e um token de conta de serviço em `DIAGNOS_TOKEN` (ou guardado pelo `diagnos login`) — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
unlocked: 2 group(s) granted
work done: 0 patient(s) on the first page
locked: 0 group(s) held after lock()
```

Código de saída: `0`; `1` em erro do cofre; `2` erro de configuração.

Sessões, reinícios e auto-unseal com OpenBao: [Sessões](../../docs/guides/sessions.pt-BR.md).
