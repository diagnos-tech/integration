# Configuration

**English** · [Português (Brasil)](configuration.pt-BR.md)

The SDK reads its configuration once, from the environment, when a `Diagnos` is built — or takes it all explicitly as
a `Settings`, with no environment involved. The CLI and the REST API embed the SDK, so every variable here applies to
them too; they only add their own flags and variables on top.

## The environment

| Variable | Default | What it does |
|---|---|---|
| `DIAGNOS_TOKEN` | unset — then the system keyring, then OpenBao | the service account token, `dgn_sk1_…`: for CI and ephemeral containers; on a workstation `diagnos login` keeps it in the keyring, on a server in OpenBao — see [Authentication](authentication.md#where-the-token-lives) |
| `DIAGNOS_API_TOKEN` | unset | **deprecated, stops working on 2027-04-15**: the legacy `apikey-<jwt>` token, with a `LegacyTokenWarning` — see [MIGRATING.md](../../MIGRATING.md#from-the-apikey--token-to-the-service-account-token-020) |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | where the vault lives; change it only for a staging or self-hosted vault |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | the timeout of each HTTP request, in seconds |
| `DIAGNOS_TIME_PRECISION` | unset | the workspace's anonymization precision — `month`, `day`, `hour`, `minute` or `second`; dates are truncated to it before sealing ([why](patients.md#dates-and-time-precision)) |
| `DIAGNOS_STORAGE_HOSTS` | `diagnosusercontent.com, r2.cloudflarestorage.com` | the hosts, and their subdomains, a presigned storage URL may point at, HTTPS only; anything else is refused before a byte leaves, so ciphertext and SSE-C keys only go where the deployment chose |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` refuses to hold a key the OS will not lock in RAM — see [below](#memory-and-process-hardening) |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` skips disabling core dumps and debugger attach at unlock — only while debugging |

No token in any of the sources raises `ConfigError` saying where it looked; a token cut short or pasted wrong raises
`TokenError` (its CRC does not match); an invalid value raises `ConfigError` naming the variable — all when the
`Diagnos` is built, before any call to the vault, never later, halfway through a request.

## OpenBao

OpenBao does two jobs, with the `openbao` extra (`pip install "diagnos[openbao]"`). It is where a server keeps the
**token** (`<prefix>/token`, stored with `diagnos login --store openbao`, read when `OPENBAO_ADDR` is set, no
`DIAGNOS_TOKEN` is set and the keyring has none). And it is where the session is saved for **auto-unseal**: on by
default only for the legacy `apikey-` token with `OPENBAO_ADDR` set, off for a service account token unless
`Diagnos(auto_unseal=True)` asks — [Sessions](sessions.md#auto-unseal-with-openbao) explains what that trades.

| Variable | Default | What it does |
|---|---|---|
| `OPENBAO_ADDR` | unset | the OpenBao server; setting it lets the SDK read the token there, and turns auto-unseal on for the legacy token |
| `OPENBAO_TOKEN` | unset | a token scoped to this deployment's paths, and nothing wider: *read* on the token, read and write on the saved session when auto-unseal is on (`apps/api/deploy/compose/openbao/policy.hcl`) |
| `OPENBAO_TOKEN_FILE` | unset | a file holding that token, read when `OPENBAO_TOKEN` is unset — how Kubernetes and Compose mount secrets |
| `OPENBAO_MOUNT` | `secret` | the KV v2 mount |
| `OPENBAO_PATH_PREFIX` | `diagnos` | the token lives at `<prefix>/token`, the saved session at `<prefix>/<workspace_id>/<key_id>` |
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
build a `Settings` yourself. It is immutable and its `repr` shows the token's identity and redacts everything secret:

```python
import os

from diagnos import Diagnos, DiagnosToken, Settings

settings = Settings(
    token=DiagnosToken.parse(os.environ["DIAGNOS_TOKEN"]),
    timeout_seconds=10,
    time_precision="day",
)
vault = Diagnos(settings=settings)
print(settings)  # token=DiagnosToken(identity='svc_…@ws_….diagnos.health', seed='<redacted>')
```

`Settings(...)` ignores the environment entirely, OpenBao and the keyring included: every field not given takes its
default. `Settings.from_env(mapping)` reads the same variables as above from any mapping (and never the keyring), and
`Diagnos(token=…)` replaces only the identity while everything else still comes from the environment.

## The CLI and the REST API

- The **CLI** takes `--token` and `--vault-url` anywhere on the line, overriding every token source and
  `DIAGNOS_VAULT_URL` for one invocation; its other global flags are in the [CLI guide](cli.md#global-options). It
  also reads `DIAGNOS_GROUP`, the security group a write seals under when `--group` is not given; and, for the legacy
  token's session agent, `DIAGNOS_AGENT` (`off` keeps every command in its own process) and
  `DIAGNOS_AGENT_IDLE_MINUTES`, how long the agent waits without a command before it ends the session (default
  `480`) — see [The legacy token in the terminal](cli.md#the-legacy-token-in-the-terminal).
- The **REST API** reads the token like the SDK — from OpenBao in a deployment — and adds its own `DIAGNOS_API_*`
  variables — certificates, host, port, allowed client names — listed in
  [Deploying](../../apps/api/deploy/README.md#environment).
