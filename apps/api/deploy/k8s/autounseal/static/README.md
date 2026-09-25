# OpenBao auto-unseal · Static key

**English** · [Português (Brasil)](README.pt-BR.md)

Wraps OpenBao's master key with a raw 32-byte AES-256-GCM-96 key you generate and hold yourself — no cloud KMS, no
second OpenBao/Vault. Verified against
[openbao.org/docs/configuration/seal/static](https://openbao.org/docs/configuration/seal/static) (v2.6.x docs) —
see `seal.hcl` for the exact stanza this overlay ships.

> [!WARNING]
> OpenBao's own documentation is blunt about this one: "carefully evaluate use of Static Key Auto Unseal to see if
> its use meets the desired security properties." A Kubernetes Secret is only as protected as your cluster's etcd
> encryption and RBAC — unlike every other overlay here, this one adds **no** separate trust boundary (no cloud KMS
> call, no second OpenBao) between "read this Secret" and "read every workspace's saved session." Use it only where
> an external, already-trusted secrets manager exists to hand this key over, or for a genuinely disposable
> environment — never as a default choice over `aws`/`gcp`/`azure`/`transit`.

## 1. Generate the key

```sh
openssl rand -base64 32
```

## 2. Apply

```sh
kubectl create secret generic openbao-static-seal \
  --from-literal=OPENBAO_STATIC_SEAL_CURRENT_KEY=<output of step 1> -n openbao
kubectl apply -k deploy/k8s/autounseal/static
```

`seal.hcl`'s `current_key_id` ships as `imgexam-static-v1` — keep the key id as-is; it is recorded by OpenBao
against every secret it seals, so renaming it (even though the packages themselves moved from `imgexam` to
`diagnos`) would break unsealing for an OpenBao that already sealed data under it. Treat it as a stable label, not a
product name.

## Rotation

Set `previous_key_id`/`previous_key` in `seal.hcl` (same `env://` pattern, a second Secret key) alongside a new
`current_key_id`/`current_key` — OpenBao re-wraps with the new key going forward while still reading anything sealed
under the previous one. Remove the `previous_*` pair only once you are certain nothing still needs it.

## Reused by Compose

Set `OPENBAO_SEAL=static` in `deploy/compose/.env` and `OPENBAO_STATIC_SEAL_CURRENT_KEY` to the same value from
step 1.
