# OpenBao auto-unseal · Azure Key Vault

**English** · [Português (Brasil)](README.pt-BR.md)

Wraps OpenBao's master key with an Azure Key Vault key. Verified against
[openbao.org/docs/configuration/seal/azurekeyvault](https://openbao.org/docs/configuration/seal/azurekeyvault)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

## 1. Create the vault and key

```sh
az keyvault create --name <vault-name> --resource-group <rg> --location <region>
az keyvault key create --vault-name <vault-name> --name diagnos-openbao-unseal \
  --kty RSA --size 2048
```

## 2. Minimal access policy

Grant the Azure AD application below exactly `get`, `wrapKey`, `unwrapKey` on this one key — via an access policy
or, on newer vaults, the equivalent RBAC role (`Key Vault Crypto User` scoped to this vault):

```sh
az keyvault set-policy --name <vault-name> \
  --spn <client-id-of-the-app-below> \
  --key-permissions get wrapKey unwrapKey
```

## 3. Federated identity credential

Register the AKS OIDC issuer + this namespace/ServiceAccount as a federated credential on the Azure AD application,
so it needs no client secret at all:

```sh
az ad app federated-credential create --id <app-object-id> --parameters '{
  "name": "diagnos-openbao",
  "issuer": "<aks-oidc-issuer-url>",
  "subject": "system:serviceaccount:openbao:openbao",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

## 4. Apply

```sh
# fill in seal.hcl's vault_name/key_name and the REPLACE_ME client id
# (the Azure AD application's client id, not a secret) before applying
kubectl apply -k deploy/k8s/autounseal/azure
```

## Reused by Compose

Set `OPENBAO_SEAL=azure` in `deploy/compose/.env`. There is no AKS workload-identity webhook outside the cluster, so
that `.env.example` uses a traditional service-principal `AZURE_CLIENT_SECRET` instead — a real secret only in that
path, never checked in.
