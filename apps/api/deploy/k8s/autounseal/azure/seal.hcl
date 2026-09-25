# 🇺🇸 `seal "azurekeyvault"` — verified against openbao.org/docs/
# configuration/seal/azurekeyvault/ (v2.6.x docs). `vault_name`/`key_name`
# are literal here (no generic env-var-only path documented for them);
# `tenant_id`/`client_id` are left absent — see the comment below — reused
# verbatim by `deploy/compose` when `OPENBAO_SEAL=azure`.
# 🇧🇷 `seal "azurekeyvault"` — verificado contra openbao.org/docs/
# configuration/seal/azurekeyvault/ (docs da v2.6.x). `vault_name`/
# `key_name` são literais aqui (sem caminho genérico só-via-env-var
# documentado para eles); `tenant_id`/`client_id` ficam ausentes — veja o
# comentário abaixo — reutilizado ao pé da letra pelo `deploy/compose`
# quando `OPENBAO_SEAL=azure`.
seal "azurekeyvault" {
  vault_name = "REPLACE_ME_KEY_VAULT_NAME"
  key_name   = "REPLACE_ME_KEY_NAME"

  # 🇺🇸 `tenant_id`/`client_id`/`client_secret` are all absent on purpose.
  # On AKS with Workload Identity, the mutating webhook that
  # `azure.workload.identity/use: "true"` (patched onto the pod by
  # `../kustomization.yaml`) opts into injects `AZURE_TENANT_ID`/
  # `AZURE_CLIENT_ID`/`AZURE_FEDERATED_TOKEN_FILE` itself, straight from
  # the ServiceAccount's `azure.workload.identity/client-id` annotation
  # (also patched there) — no `client_secret` exists anywhere, which is the
  # whole point of federation over a service-principal secret.
  # `deploy/compose`'s `.env.example` (`OPENBAO_SEAL=azure`) sets
  # `AZURE_TENANT_ID`/`AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET` instead, since
  # nothing outside AKS can inject a federated token.
  # 🇧🇷 `tenant_id`/`client_id`/`client_secret` ficam ausentes de propósito.
  # No AKS com Workload Identity, o webhook mutante que
  # `azure.workload.identity/use: "true"` (aplicado ao pod por
  # `../kustomization.yaml`) ativa injeta `AZURE_TENANT_ID`/
  # `AZURE_CLIENT_ID`/`AZURE_FEDERATED_TOKEN_FILE` sozinho, direto da
  # anotação `azure.workload.identity/client-id` do ServiceAccount (também
  # aplicada ali) — nenhum `client_secret` existe em lugar nenhum, que é o
  # ponto inteiro de federação em vez de um segredo de service principal.
  # O `.env.example` do `deploy/compose` (`OPENBAO_SEAL=azure`) define
  # `AZURE_TENANT_ID`/`AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET` em vez disso,
  # já que nada fora do AKS consegue injetar um token federado.
}
