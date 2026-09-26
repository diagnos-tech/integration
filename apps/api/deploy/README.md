# Deploying `diagnos-api`

**English** · [Português (Brasil)](README.pt-BR.md)

The API is a thin shell over the SDK. It needs three things: the service account token, a certificate pair to serve
HTTPS, and the CA that signs the **client** certificates — mutual TLS is the only authentication it accepts, so a
request without a valid client certificate never reaches application code. With OpenBao configured, a pod restart
resumes the SDK session without a human approving again.

## Environment

| Variable | Required | Meaning |
|---|---|---|
| `DIAGNOS_API_TOKEN` | yes | Service account token (`apikey-…`). |
| `DIAGNOS_API_MTLS_CA_FILE` | yes | PEM bundle of the CA(s) allowed to sign client certificates. |
| `DIAGNOS_API_TLS_CERT_FILE` / `DIAGNOS_API_TLS_KEY_FILE` | yes | Server certificate and key (PEM). |
| `DIAGNOS_API_HOST` / `DIAGNOS_API_PORT` | no | Default `0.0.0.0` / `8443`. |
| `DIAGNOS_API_ALLOWED_CLIENT_CN` | no | Comma-separated CNs; when set, only these client certificates pass. |
| `OPENBAO_ADDR` / `OPENBAO_TOKEN` / `OPENBAO_MOUNT` / `OPENBAO_PATH_PREFIX` | no | Auto-unseal (see [`docs/PROTOCOL.md` §11](../../../docs/PROTOCOL.md)). |
| `OPENBAO_TOKEN_FILE` | no | A file to read the OpenBao token from when `OPENBAO_TOKEN` is unset — how Compose (`deploy/compose`) and file-mounted Kubernetes Secrets hand it over without an environment value. |
| `DIAGNOS_VAULT_URL` | no | Default `https://vault.diagnos.health`. |
| `DIAGNOS_STORAGE_HOSTS` | no | Default `diagnosusercontent.com, r2.cloudflarestorage.com` — the storage hosts presigned URLs may point at. |

Without OpenBao, the first start prints the approval link and code to the container log; a workspace admin approves
once per process lifetime.

## Kubernetes

```sh
kubectl apply -k deploy/k8s     # edit the Secret first
```

`deploy/k8s` ships a Deployment (1 replica — the SDK session is per process; scale with OpenBao and one service
account per replica if you need more), a ClusterIP Service on 8443, a Secret template and a ConfigMap. Client
certificates are the callers' responsibility; the CA bundle is mounted read-only.

## Docker Compose

`deploy/compose` is the fastest way to see the whole stack — OpenBao and `diagnos-api` — running together with
nothing pre-existing:

```sh
cd deploy/compose
cp .env.example .env   # fill in DIAGNOS_API_TOKEN, then `diagnos status` for the two ids
# certs/ needs clients-ca.pem/server.pem/server-key.pem — see this file's own openssl recipe below
docker compose up
```

A one-shot `openbao-bootstrap` service initialises OpenBao (or resumes, on later runs), enables the KV v2 mount,
writes the scoped `diagnos-sdk` policy, and mints the token the API reads — `diagnos-api` only starts once that
finishes successfully. [`deploy/compose/README.md`](compose/README.md) has the full walkthrough.

> [!WARNING]
> **Staging only, read before using this.** The default `OPENBAO_SEAL=shamir` keeps OpenBao's unseal keys sitting on
> a local Docker volume so the bootstrap service can re-unseal on every restart without a human — a deliberate
> convenience for a disposable environment, and a real widening of who can read every saved session if this
> configuration ever runs anywhere that matters. `deploy/compose/.env.example` documents the `aws`/`gcp`/`azure`/
> `transit` alternatives, sharing the exact same `seal.hcl` files as the Kubernetes overlays below.

## OpenBao on Kubernetes

`deploy/k8s/openbao` is a kustomize base for OpenBao itself (namespace `openbao`, a one-replica raft StatefulSet,
the ClusterIP Service the `OPENBAO_ADDR` above already assumes) — a separate concern from `deploy/k8s` (the API), so
a platform team can own it independently:

```sh
kubectl apply -k deploy/k8s/openbao          # unseals manually (Shamir)
# or, with real auto-unseal:
kubectl apply -k deploy/k8s/autounseal/aws   # aws | gcp | azure | transit | static | shamir
```

`deploy/k8s/autounseal/<provider>` overlays the base with the seal each KMS needs — every one verified field-by-field
against openbao.org's own docs, not remembered from HashiCorp Vault (the two have diverged):

| Provider | What it needs |
|---|---|
| [`aws`](k8s/autounseal/aws/README.md) | IRSA (`eks.amazonaws.com/role-arn`) + `kms:Encrypt`/`Decrypt`/`DescribeKey` on one key |
| [`gcp`](k8s/autounseal/gcp/README.md) | Workload Identity (`iam.gke.io/gcp-service-account`) + `roles/cloudkms.cryptoKeyEncrypterDecrypter` |
| [`azure`](k8s/autounseal/azure/README.md) | Workload identity federation (`azure.workload.identity/client-id`) + Key Vault `get`/`wrapKey`/`unwrapKey` |
| [`transit`](k8s/autounseal/transit/README.md) | A token, scoped to `encrypt`/`decrypt` on one key, from another already-unsealed OpenBao/Vault |
| [`static`](k8s/autounseal/static/README.md) | A 32-byte key you generate and hold — read that overlay's security warning first |
| [`shamir`](k8s/autounseal/shamir/README.md) | Nothing — the fallback; manual `bao operator unseal` after every restart |

After the first `kubectl apply`, bootstrap OpenBao itself (`kv-v2` mount, the `diagnos-sdk` policy, the token) by
running the same script the Compose bootstrap uses, inside the already-running pod:
`deploy/k8s/openbao/bootstrap-configmap.yaml` has the exact command and where the resulting token goes.

## Memory locking

The SDK calls `mlock()` on session keys and group DEKs so the kernel never pages them to swap —
[`docs/PROTOCOL.md`](../../../docs/PROTOCOL.md)'s "never sends a key to the vault" guarantee would not mean much if the
key could still end up on a disk block. Three things have to line up for that call to succeed in a container:

1. **`CAP_IPC_LOCK`** — `deploy/k8s/deployment.yaml`'s `capabilities.add: [IPC_LOCK]` and `deploy/compose`'s
   `cap_add: [IPC_LOCK]` both grant it; the image itself carries `cap_ipc_lock` as a file capability so a non-root
   process can use it.
2. **`RLIMIT_MEMLOCK`** — the default 64 KiB is not enough; `deploy/compose`'s `ulimits.memlock: { soft: -1, hard:
   -1 }` removes the limit entirely (Kubernetes has no per-container ulimit field, which is exactly why the
   capability above matters more there).
3. **`DIAGNOS_MEMORY_LOCK=require`** (commented out in `deploy/k8s/configmap.yaml`) — makes the process refuse to
   start if `mlock` fails instead of silently continuing with swappable keys; uncomment it once the first two are
   confirmed working on your nodes.

Separately, `DIAGNOS_HARDEN_PROCESS` (default `"1"`) disables core dumps and `ptrace` attach for the process — set
`"0"` only on a deployment you are actively debugging, and revert right after.
