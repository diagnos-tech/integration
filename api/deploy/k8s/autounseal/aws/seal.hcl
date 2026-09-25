# 🇺🇸 `seal "awskms"` — verified against openbao.org/docs/configuration/
# seal/awskms/ (v2.6.x docs). Reused verbatim by `deploy/compose` when
# `OPENBAO_SEAL=aws` (see that directory's `docker-compose.yml`), so this
# file has to work standing alone with only environment variables for
# credentials, never assuming Kubernetes' IRSA is the only way in.
# 🇧🇷 `seal "awskms"` — verificado contra openbao.org/docs/configuration/
# seal/awskms/ (docs da v2.6.x). Reutilizado ao pé da letra pelo
# `deploy/compose` quando `OPENBAO_SEAL=aws` (veja o `docker-compose.yml`
# daquele diretório), então este arquivo precisa funcionar sozinho só com
# variáveis de ambiente para credencial, sem presumir que o IRSA do
# Kubernetes é o único jeito de entrar.
seal "awskms" {
  # 🇺🇸 The one field with no natural "ambient identity" substitute: which
  # key. Not secret — an ARN, key id, or `alias/<name>` — safe to commit
  # once filled in. `README.md` has the exact IAM permissions this key's
  # policy needs to grant this seal's caller.
  # 🇧🇷 O único campo sem substituto natural de "identidade ambiente": qual
  # chave. Não é segredo — um ARN, id de chave, ou `alias/<name>` — seguro
  # de commitar depois de preenchido. `README.md` tem as permissões IAM
  # exatas que a política dessa chave precisa conceder para quem chama este
  # seal.
  kms_key_id = "REPLACE_ME_KMS_KEY_ID_OR_ARN"

  # 🇺🇸 `region`/`access_key`/`secret_key`/`session_token` are deliberately
  # absent: OpenBao falls back to `AWS_REGION`/`AWS_ACCESS_KEY_ID`/
  # `AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` (the AWS SDK's own standard
  # names) when a field is unset. `../kustomization.yaml` patches
  # `AWS_REGION` onto the StatefulSet directly; the three credential
  # variables are meant to stay unset in Kubernetes; the ServiceAccount's
  # `eks.amazonaws.com/role-arn` annotation (also patched there) is what
  # supplies temporary credentials with zero secret material in this repo
  # at all. `deploy/compose/.env.example` sets the same variables for a
  # host that has no IRSA-equivalent to fall back on.
  # 🇧🇷 `region`/`access_key`/`secret_key`/`session_token` ficam de
  # propósito ausentes: o OpenBao cai para `AWS_REGION`/`AWS_ACCESS_KEY_ID`/
  # `AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` (os nomes padrão do próprio
  # SDK da AWS) quando um campo não está definido. `../kustomization.yaml`
  # aplica um patch de `AWS_REGION` direto no StatefulSet; as três
  # variáveis de credencial devem ficar sem definir no Kubernetes; a
  # anotação `eks.amazonaws.com/role-arn` do ServiceAccount (também
  # aplicada por patch ali) é o que fornece credenciais temporárias sem
  # nenhum material secreto neste repositório. O
  # `deploy/compose/.env.example` define as mesmas variáveis para um host
  # sem equivalente de IRSA para cair de volta.
}
