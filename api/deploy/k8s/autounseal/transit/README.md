# OpenBao auto-unseal · Transit (another OpenBao/Vault)

**English** · [Português (Brasil)](README.pt-BR.md)

Wraps this OpenBao's master key using the transit engine of another, already-unsealed OpenBao or Vault. Verified
against [openbao.org/docs/configuration/seal/transit](https://openbao.org/docs/configuration/seal/transit) (v2.6.x
docs) — see `seal.hcl` for the exact stanza this overlay ships.

## 1. On the *other*, already-unsealed instance

```sh
bao secrets enable transit
bao write -f transit/keys/diagnos-openbao-unseal
```

## 2. Minimal policy for the token below

The token this seal authenticates with needs `update` on exactly this key's `encrypt`/`decrypt` paths — nothing
else:

```hcl
path "transit/encrypt/diagnos-openbao-unseal" {
  capabilities = ["update"]
}
path "transit/decrypt/diagnos-openbao-unseal" {
  capabilities = ["update"]
}
```

```sh
bao policy write diagnos-openbao-unseal ./that-policy.hcl
bao token create -orphan -renewable=true -policy=diagnos-openbao-unseal -format=json
```

## 3. Apply

```sh
# fill in seal.hcl's address/key_name, then set the real token instead
# of applying secret.yaml's REPLACE_ME
kubectl create secret generic openbao-transit-unseal \
  --from-literal=VAULT_TOKEN=<token from step 2> -n openbao
kubectl apply -k deploy/k8s/autounseal/transit
```

`disable_renewal` defaults to `false` (`seal.hcl` leaves it unset) — a renewable orphan token from step 2 keeps
itself alive; a non-renewable one needs manual reissue before it expires.

## Reused by Compose

Set `OPENBAO_SEAL=transit` in `deploy/compose/.env` with the same
`VAULT_ADDR`/`VAULT_TOKEN`/`VAULT_TRANSIT_SEAL_KEY_NAME`/`VAULT_TRANSIT_SEAL_MOUNT_PATH`.
