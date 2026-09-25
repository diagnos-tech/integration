# OpenBao auto-unseal · Transit (another OpenBao/Vault)

🇺🇸 Wraps this OpenBao's master key using the transit engine of another,
already-unsealed OpenBao or Vault. Verified against
[openbao.org/docs/configuration/seal/transit](https://openbao.org/docs/configuration/seal/transit)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

🇧🇷 Envolve a master key deste OpenBao usando o transit engine de outro
OpenBao ou Vault já desselado. Verificado contra
[openbao.org/docs/configuration/seal/transit](https://openbao.org/docs/configuration/seal/transit)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay
traz.

## 1. On the *other*, already-unsealed instance · Na *outra* instância, já desselada

```sh
bao secrets enable transit
bao write -f transit/keys/diagnos-openbao-unseal
```

## 2. Minimal policy for the token below · Política mínima para o token abaixo

🇺🇸 The token this seal authenticates with needs `update` on exactly this
key's `encrypt`/`decrypt` paths — nothing else:

🇧🇷 O token com o qual este seal se autentica precisa de `update` só nos
paths de `encrypt`/`decrypt` desta chave — nada mais:

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

## 3. Apply · Aplicar

```sh
# 🇺🇸 fill in seal.hcl's address/key_name, then set the real token instead
#    of applying secret.yaml's REPLACE_ME
# 🇧🇷 preencha o address/key_name de seal.hcl, depois defina o token de
#    verdade em vez de aplicar o REPLACE_ME de secret.yaml
kubectl create secret generic openbao-transit-unseal \
  --from-literal=VAULT_TOKEN=<token from step 2> -n openbao
kubectl apply -k deploy/k8s/autounseal/transit
```

🇺🇸 `disable_renewal` defaults to `false` (`seal.hcl` leaves it unset) — a
renewable orphan token from step 2 keeps itself alive; a non-renewable one
needs manual reissue before it expires.

🇧🇷 `disable_renewal` tem padrão `false` (`seal.hcl` deixa sem definir) — um
token órfão renovável do passo 2 se mantém vivo sozinho; um não-renovável
precisa de reemissão manual antes de expirar.

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 Set `OPENBAO_SEAL=transit` in `deploy/compose/.env` with the same
`VAULT_ADDR`/`VAULT_TOKEN`/`VAULT_TRANSIT_SEAL_KEY_NAME`/
`VAULT_TRANSIT_SEAL_MOUNT_PATH`.

🇧🇷 Defina `OPENBAO_SEAL=transit` no `deploy/compose/.env` com os mesmos
`VAULT_ADDR`/`VAULT_TOKEN`/`VAULT_TRANSIT_SEAL_KEY_NAME`/
`VAULT_TRANSIT_SEAL_MOUNT_PATH`.
