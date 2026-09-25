# OpenBao auto-unseal · Transit (outro OpenBao/Vault)

[English](README.md) · **Português (Brasil)**

Envolve a master key deste OpenBao usando o transit engine de outro OpenBao ou Vault já desselado. Verificado
contra [openbao.org/docs/configuration/seal/transit](https://openbao.org/docs/configuration/seal/transit) (docs da
v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay traz.

## 1. Na *outra* instância, já desselada

```sh
bao secrets enable transit
bao write -f transit/keys/diagnos-openbao-unseal
```

## 2. Política mínima para o token abaixo

O token com o qual este seal se autentica precisa de `update` só nos paths de `encrypt`/`decrypt` desta chave — nada
mais:

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

## 3. Aplicar

```sh
# preencha o address/key_name de seal.hcl, depois defina o token de
# verdade em vez de aplicar o REPLACE_ME de secret.yaml
kubectl create secret generic openbao-transit-unseal \
  --from-literal=VAULT_TOKEN=<token from step 2> -n openbao
kubectl apply -k deploy/k8s/autounseal/transit
```

`disable_renewal` tem padrão `false` (`seal.hcl` deixa sem definir) — um token órfão renovável do passo 2 se mantém
vivo sozinho; um não-renovável precisa de reemissão manual antes de expirar.

## Reaproveitado pelo Compose

Defina `OPENBAO_SEAL=transit` no `deploy/compose/.env` com os mesmos
`VAULT_ADDR`/`VAULT_TOKEN`/`VAULT_TRANSIT_SEAL_KEY_NAME`/`VAULT_TRANSIT_SEAL_MOUNT_PATH`.
