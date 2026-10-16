# Example: Lock the session

**English** · [Português (Brasil)](README.pt-BR.md)

Unlocks, does some work and ends the session on purpose in a `finally`: `lock()` ends it on the vault (best effort) and always wipes the keys from this process. Leaving a `with` block does not do that — it only closes the HTTP clients, so a restarting worker can resume its session.

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, and a service account token in `DIAGNOS_TOKEN` (or stored by `diagnos login`) — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
unlocked: 2 group(s) granted
work done: 0 patient(s) on the first page
locked: 0 group(s) held after lock()
```

Exit code: `0`; `1` on a vault error; `2` configuration error.

Sessions, restarts and OpenBao auto-unseal: [Sessions](../../docs/guides/sessions.md).
