# Example: Error handling

**English** · [Português (Brasil)](README.pt-BR.md)

Part one needs no vault: `advice()` maps each exception class (`ClockSkewError`, `ScopeMissingError`, `CredentialRevokedError`, `NotFoundError`, `RateLimitError`, `TokenError`…) to a message that says what to do, most specific class first. Part two is a live run: it provokes a real `NotFoundError`, handles it, and wraps a call in `with_retries` (exponential pause, only for `429` and `5xx`). The SDK already retries what is safe; this is only for a longer pause.

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, and a service account token in `DIAGNOS_TOKEN` (or stored by `diagnos login`) — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
ClockSkewError: this machine's clock is 95 s ahead (limit ±60 s): enable NTP, retrying will not help · o relógio …
ScopeMissingError: ask an admin for a token with create on patients in group sg_radiology · peça a um admin …
CredentialRevokedError: create a new token for the service account and run `diagnos login` · …
…
handled DocumentNotFound (404): no such document or file: check the id · documento ou arquivo inexistente: …
live call ok: 0 patient(s) on the page
```

Exit code: `0`; `1` when the live run hits an error it cannot handle (the advice is on `stderr`).

Every exception and what the SDK retries: [Errors](../../docs/guides/errors.md).
