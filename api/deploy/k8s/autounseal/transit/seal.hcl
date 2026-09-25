# 🇺🇸 `seal "transit"` — verified against openbao.org/docs/configuration/
# seal/transit/ (v2.6.x docs). Wraps this OpenBao's master key using the
# transit engine of a *different*, already-unsealed OpenBao/Vault —
# useful when that other instance already has a real KMS-backed auto-
# unseal and you would rather not provision a second cloud KMS key just
# for this one. Reused verbatim by `deploy/compose` when
# `OPENBAO_SEAL=transit`.
# 🇧🇷 `seal "transit"` — verificado contra openbao.org/docs/configuration/
# seal/transit/ (docs da v2.6.x). Envolve a master key deste OpenBao usando
# o transit engine de um *outro* OpenBao/Vault já desselado — útil quando
# essa outra instância já tem um auto-unseal de verdade apoiado em KMS e
# você prefere não provisionar uma segunda chave de KMS de nuvem só para
# esta. Reutilizado ao pé da letra pelo `deploy/compose` quando
# `OPENBAO_SEAL=transit`.
seal "transit" {
  address    = "REPLACE_ME_TRANSIT_OPENBAO_ADDR"
  key_name   = "REPLACE_ME_TRANSIT_KEY_NAME"
  mount_path = "transit/"

  # 🇺🇸 `token` is deliberately absent: `../kustomization.yaml` patches
  # `VAULT_TOKEN` onto the StatefulSet from the `openbao-transit-unseal`
  # Secret (`secret.yaml`, template only — `README.md` has the policy that
  # token needs). `deploy/compose`'s `.env.example` sets the same
  # `VAULT_TOKEN` for the non-Kubernetes path.
  # 🇧🇷 `token` fica ausente de propósito: `../kustomization.yaml` aplica
  # por patch `VAULT_TOKEN` no StatefulSet a partir do Secret
  # `openbao-transit-unseal` (`secret.yaml`, só modelo — `README.md` tem a
  # política que esse token precisa). O `.env.example` do `deploy/compose`
  # define o mesmo `VAULT_TOKEN` para o caminho fora do Kubernetes.
}
