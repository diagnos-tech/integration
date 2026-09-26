# Configuration

**English** · [Português (Brasil)](configuration.pt-BR.md)

The SDK reads its configuration once, from the environment, when a `Diagnos` is built — or takes it all explicitly as
a `Settings`, with no environment involved. The CLI and the REST API embed the SDK, so every variable here applies to
them too; they only add their own flags and variables on top.

## The environment

| Variable | Default | What it does |
|---|---|---|
| `DIAGNOS_API_TOKEN` | — (required) | the service-account token, `apikey-<jwt>` — see [Authentication](authentication.md) |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | where the vault lives; change it only for a staging or self-hosted vault |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | the timeout of each HTTP request, in seconds |
| `DIAGNOS_TIME_PRECISION` | unset | the workspace's anonymization precision — `month`, `day`, `hour`, `minute` or `second`; dates are truncated to it before sealing ([why](patients.md#dates-and-time-precision)) |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` refuses to hold a key the OS will not lock in RAM — see [below](#memory-and-process-hardening) |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` skips disabling core dumps and debugger attach at unlock — only while debugging |

An invalid value raises `ConfigError` naming the variable, when the `Diagnos` is built — never later, halfway
through a request.

## OpenBao

Auto-unseal is on exactly when `OPENBAO_ADDR` is set, and needs the `openbao` extra (`pip install "diagnos[openbao]"`).
[Sessions](sessions.md#auto-unseal-with-openbao) explains what it trades.

| Variable | Default | What it does |
|---|---|---|
| `OPENBAO_ADDR` | unset | the OpenBao server; setting it turns auto-unseal on |
| `OPENBAO_TOKEN` | unset | a token scoped to this service account's path, and nothing wider |
| `OPENBAO_TOKEN_FILE` | unset | a file holding that token, read when `OPENBAO_TOKEN` is unset — how Kubernetes and Compose mount secrets |
| `OPENBAO_MOUNT` | `secret` | the KV v2 mount |
| `OPENBAO_PATH_PREFIX` | `diagnos` | the saved session lives at `<prefix>/<workspace_id>/<account_id>` |
| `OPENBAO_NAMESPACE` | unset | an OpenBao namespace, if you use them |

## Memory and process hardening

Every key the SDK holds lives in page-locked memory managed by its Rust enclave, so it never reaches swap. Locking
counts against `ulimit -l` — often 64 KiB in a container. When the OS refuses, the SDK keeps every other
protection and emits one `MemoryLockWarning`; with `DIAGNOS_MEMORY_LOCK=require` it refuses to run that way instead.

```python
import diagnos

status = diagnos.memory_status()
print(status["lock_policy"], status["backend"], status["unlocked_allocations"])
```

`memory_status()` says what the enclave guarantees on this machine right now: the policy, whether guard pages and
wipe-on-fork are available, how many allocations could not be locked, and whether `CAP_IPC_LOCK` is permitted. To make
locking succeed in a container, grant `CAP_IPC_LOCK` or raise the limit —
[Deploying](../../apps/api/deploy/README.md#memory-locking) has the three settings, and
[the enclave](../../apps/sdk/native/README.md#operating-it) the reasoning.

`DIAGNOS_HARDEN_PROCESS=1`, the default, disables core dumps and denies debugger attach the moment the process
unlocks — the moment it starts holding clinical keys. Set `0` only to attach a debugger, and revert right after.

## Without the environment: `Settings`

For tests, for a process that talks as several service accounts, or when configuration comes from somewhere else,
build a `Settings` yourself. It is immutable and its `repr` redacts both tokens:

```python
import os

from diagnos import Diagnos, Settings

settings = Settings(
    api_token=os.environ["DIAGNOS_API_TOKEN"],
    timeout_seconds=10,
    time_precision="day",
)
vault = Diagnos(settings=settings)
print(settings)  # api_token='apikey-…' — never the token itself
```

`Settings(...)` ignores the environment entirely, OpenBao included: every field not given takes its default.
`Settings.from_env(mapping)` reads the same variables as above from any mapping, and `Diagnos(token=…)` replaces only
the token while everything else still comes from the environment.

## The CLI and the REST API

- The **CLI** takes `--token` and `--vault-url` before the subcommand, overriding `DIAGNOS_API_TOKEN` and
  `DIAGNOS_VAULT_URL` for one invocation; its other global flags are in the [CLI guide](cli.md#global-options).
- The **REST API** adds its own `DIAGNOS_API_*` variables — certificates, host, port, allowed client names — listed
  in [Deploying](../../apps/api/deploy/README.md#environment).
