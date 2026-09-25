# 🇺🇸 `seal "gcpckms"` — verified against openbao.org/docs/configuration/
# seal/gcpckms/ (v2.6.x docs). `project`/`region`/`key_ring`/`crypto_key`
# are documented as required *in the config file itself* (unlike AWS'
# fields, these four have no env-var-only path in the base seal docs), so
# they are literal here rather than deferred to environment — reused
# verbatim by `deploy/compose` when `OPENBAO_SEAL=gcp`.
# 🇧🇷 `seal "gcpckms"` — verificado contra openbao.org/docs/configuration/
# seal/gcpckms/ (docs da v2.6.x). `project`/`region`/`key_ring`/
# `crypto_key` são documentados como obrigatórios *no próprio arquivo de
# config* (diferente dos campos do AWS, esses quatro não têm caminho só-
# via-env-var na doc base do seal), então ficam literais aqui em vez de
# adiados para o ambiente — reutilizado ao pé da letra pelo
# `deploy/compose` quando `OPENBAO_SEAL=gcp`.
seal "gcpckms" {
  project    = "REPLACE_ME_GCP_PROJECT"
  region     = "REPLACE_ME_KEY_RING_LOCATION"
  key_ring   = "REPLACE_ME_KEY_RING"
  crypto_key = "REPLACE_ME_CRYPTO_KEY"

  # 🇺🇸 `credentials` is deliberately absent: with no path given, the
  # underlying Google client library falls back to Application Default
  # Credentials — on GKE with Workload Identity (the ServiceAccount
  # annotation `../kustomization.yaml` patches in), that means the ambient
  # federated identity, no key file anywhere. Outside Kubernetes (the
  # Compose path, `OPENBAO_SEAL=gcp`), set `GOOGLE_APPLICATION_CREDENTIALS`
  # in `.env` to a mounted service-account JSON key instead.
  # 🇧🇷 `credentials` fica ausente de propósito: sem um caminho informado, a
  # biblioteca cliente do Google cai para Application Default Credentials —
  # no GKE com Workload Identity (a anotação do ServiceAccount que o
  # `../kustomization.yaml` aplica por patch), isso significa a identidade
  # federada ambiente, sem arquivo de chave nenhum. Fora do Kubernetes (o
  # caminho do Compose, `OPENBAO_SEAL=gcp`), defina
  # `GOOGLE_APPLICATION_CREDENTIALS` no `.env` para uma chave JSON de
  # service account montada em vez disso.
}
