# 🇺🇸 `seal "static"` — verified against openbao.org/docs/configuration/
# seal/static/ (v2.6.x docs). Wraps the master key with a raw 32-byte
# AES-256-GCM-96 key you generate and hold yourself — no cloud KMS, no
# second OpenBao/Vault. `openbao.org` calls this out explicitly: use it
# only when some other trusted secrets manager already exists in the
# operating environment to hand this key over safely, since OpenBao itself
# adds no protection around it beyond what `env://` already gives (an
# environment variable, not a file on disk). Reused verbatim by
# `deploy/compose` when `OPENBAO_SEAL=static`.
# 🇧🇷 `seal "static"` — verificado contra openbao.org/docs/configuration/
# seal/static/ (docs da v2.6.x). Envolve a master key com uma chave crua de
# 32 bytes AES-256-GCM-96 que você gera e guarda por conta própria — sem
# KMS de nuvem, sem um segundo OpenBao/Vault. O próprio openbao.org avisa
# isso explicitamente: use só quando já existe algum outro gerenciador de
# segredos confiável no ambiente operacional para entregar esta chave com
# segurança, já que o OpenBao em si não soma proteção nenhuma além do que
# `env://` já dá (uma variável de ambiente, não um arquivo em disco).
# Reutilizado ao pé da letra pelo `deploy/compose` quando
# `OPENBAO_SEAL=static`.
seal "static" {
  # 🇺🇸 A stable label, not secret material — safe to commit once chosen;
  # it is how a future rotation's `previous_key_id` refers back to this
  # one.
  # 🇧🇷 Um rótulo estável, não é material secreto — seguro de commitar
  # depois de escolhido; é como um `previous_key_id` de uma rotação futura
  # se refere de volta a esta.
  current_key_id = "imgexam-static-v1"

  # 🇺🇸 `env://` — the actual 32-byte key never touches this file or any
  # ConfigMap; `../kustomization.yaml` patches this variable onto the
  # StatefulSet from the `openbao-static-seal` Secret (`secret.yaml`,
  # template only).
  # 🇧🇷 `env://` — a chave de 32 bytes de fato nunca toca este arquivo nem
  # nenhum ConfigMap; `../kustomization.yaml` aplica esta variável por
  # patch no StatefulSet a partir do Secret `openbao-static-seal`
  # (`secret.yaml`, só modelo).
  current_key = "env://OPENBAO_STATIC_SEAL_CURRENT_KEY"

  # 🇺🇸 During a rotation only: set `previous_key_id`/`previous_key` (same
  # `env://` pattern, a second variable) so already-sealed data wrapped
  # under the old key can still be read while everything new uses
  # `current_key`.
  # 🇧🇷 Só durante uma rotação: defina `previous_key_id`/`previous_key`
  # (mesmo padrão `env://`, uma segunda variável) para dado já selado sob a
  # chave antiga continuar legível enquanto tudo novo usa `current_key`.
}
