# Exemplo: Tratamento de erros

[English](README.md) · **Português (Brasil)**

A parte um não precisa de cofre: `advice()` mapeia cada classe de exceção (`ClockSkewError`, `ScopeMissingError`, `CredentialRevokedError`, `NotFoundError`, `RateLimitError`, `TokenError`…) para uma mensagem que diz o que fazer, da classe mais específica para a mais geral. A parte dois é uma execução real: provoca um `NotFoundError` de verdade, trata, e embrulha uma chamada em `with_retries` (pausa exponencial, só para `429` e `5xx`). O SDK já retenta o que é seguro; isto é só para uma pausa maior.

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, e um token de conta de serviço em `DIAGNOS_TOKEN` (ou guardado pelo `diagnos login`) — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
ClockSkewError: this machine's clock is 95 s ahead (limit ±60 s): enable NTP, retrying will not help · o relógio …
ScopeMissingError: ask an admin for a token with create on patients in group sg_radiology · peça a um admin …
CredentialRevokedError: create a new token for the service account and run `diagnos login` · …
…
handled DocumentNotFound (404): no such document or file: check the id · documento ou arquivo inexistente: …
live call ok: 0 patient(s) on the page
```

Código de saída: `0`; `1` quando a execução real encontra um erro que não sabe tratar (o conselho vai no `stderr`).

Toda exceção e o que o SDK retenta: [Erros](../../docs/guides/errors.pt-BR.md).
