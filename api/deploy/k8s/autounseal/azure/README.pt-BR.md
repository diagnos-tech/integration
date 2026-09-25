# OpenBao auto-unseal · Azure Key Vault

[English](README.md) · **Português (Brasil)**

Envolve a master key do OpenBao com uma chave do Azure Key Vault. Verificado contra
[openbao.org/docs/configuration/seal/azurekeyvault](https://openbao.org/docs/configuration/seal/azurekeyvault)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay traz.

## 1. Criar o vault e a chave

```sh
az keyvault create --name <vault-name> --resource-group <rg> --location <region>
az keyvault key create --vault-name <vault-name> --name diagnos-openbao-unseal \
  --kty RSA --size 2048
```

## 2. Access policy mínima

Conceda à aplicação do Azure AD abaixo exatamente `get`, `wrapKey`, `unwrapKey` nesta única chave — via access
policy ou, em vaults mais novos, o papel RBAC equivalente (`Key Vault Crypto User` restrito a este vault):

```sh
az keyvault set-policy --name <vault-name> \
  --spn <client-id-of-the-app-below> \
  --key-permissions get wrapKey unwrapKey
```

## 3. Credencial de identidade federada

Registre o emissor OIDC do AKS + este namespace/ServiceAccount como uma credencial federada na aplicação do Azure
AD, para ela não precisar de nenhum client secret:

```sh
az ad app federated-credential create --id <app-object-id> --parameters '{
  "name": "diagnos-openbao",
  "issuer": "<aks-oidc-issuer-url>",
  "subject": "system:serviceaccount:openbao:openbao",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

## 4. Aplicar

```sh
# preencha o vault_name/key_name de seal.hcl e o REPLACE_ME de client
# id (o client id da aplicação do Azure AD, não é segredo) antes de
# aplicar
kubectl apply -k deploy/k8s/autounseal/azure
```

## Reaproveitado pelo Compose

Defina `OPENBAO_SEAL=azure` no `deploy/compose/.env`. Não existe webhook de workload identity do AKS fora do
cluster, então aquele `.env.example` usa um `AZURE_CLIENT_SECRET` de service principal tradicional em vez disso —
um segredo de verdade só nesse caminho, nunca commitado.
