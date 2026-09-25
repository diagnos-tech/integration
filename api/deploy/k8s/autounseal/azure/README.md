# OpenBao auto-unseal · Azure Key Vault

🇺🇸 Wraps OpenBao's master key with an Azure Key Vault key. Verified against
[openbao.org/docs/configuration/seal/azurekeyvault](https://openbao.org/docs/configuration/seal/azurekeyvault)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

🇧🇷 Envolve a master key do OpenBao com uma chave do Azure Key Vault.
Verificado contra
[openbao.org/docs/configuration/seal/azurekeyvault](https://openbao.org/docs/configuration/seal/azurekeyvault)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay
traz.

## 1. Create the vault and key · Criar o vault e a chave

```sh
az keyvault create --name <vault-name> --resource-group <rg> --location <region>
az keyvault key create --vault-name <vault-name> --name diagnos-openbao-unseal \
  --kty RSA --size 2048
```

## 2. Minimal access policy · Access policy mínima

🇺🇸 Grant the Azure AD application below exactly `get`, `wrapKey`,
`unwrapKey` on this one key — via an access policy or, on newer vaults,
the equivalent RBAC role (`Key Vault Crypto User` scoped to this vault):

🇧🇷 Conceda à aplicação do Azure AD abaixo exatamente `get`, `wrapKey`,
`unwrapKey` nesta única chave — via access policy ou, em vaults mais
novos, o papel RBAC equivalente (`Key Vault Crypto User` restrito a este
vault):

```sh
az keyvault set-policy --name <vault-name> \
  --spn <client-id-of-the-app-below> \
  --key-permissions get wrapKey unwrapKey
```

## 3. Federated identity credential · Credencial de identidade federada

🇺🇸 Register the AKS OIDC issuer + this namespace/ServiceAccount as a
federated credential on the Azure AD application, so it needs no client
secret at all:

🇧🇷 Registre o emissor OIDC do AKS + este namespace/ServiceAccount como uma
credencial federada na aplicação do Azure AD, para ela não precisar de
nenhum client secret:

```sh
az ad app federated-credential create --id <app-object-id> --parameters '{
  "name": "diagnos-openbao",
  "issuer": "<aks-oidc-issuer-url>",
  "subject": "system:serviceaccount:openbao:openbao",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

## 4. Apply · Aplicar

```sh
# 🇺🇸 fill in seal.hcl's vault_name/key_name and the REPLACE_ME client id
#    (the Azure AD application's client id, not a secret) before applying
# 🇧🇷 preencha o vault_name/key_name de seal.hcl e o REPLACE_ME de client
#    id (o client id da aplicação do Azure AD, não é segredo) antes de
#    aplicar
kubectl apply -k deploy/k8s/autounseal/azure
```

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 Set `OPENBAO_SEAL=azure` in `deploy/compose/.env`. There is no AKS
workload-identity webhook outside the cluster, so that `.env.example` uses
a traditional service-principal `AZURE_CLIENT_SECRET` instead — a real
secret only in that path, never checked in.

🇧🇷 Defina `OPENBAO_SEAL=azure` no `deploy/compose/.env`. Não existe webhook
de workload identity do AKS fora do cluster, então aquele `.env.example`
usa um `AZURE_CLIENT_SECRET` de service principal tradicional em vez disso
— um segredo de verdade só nesse caminho, nunca commitado.
