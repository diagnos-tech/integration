# 🇺🇸 Policy `diagnos-token-writer`: the only thing the *writer* token may do —
# store, rotate or remove the diagnos service account token at
# `secret/diagnos/token` (`diagnos login --store openbao`, the `login`
# service in `../docker-compose.yml`). `bootstrap.sh` issues it into the
# `openbao-admin` volume, which the `api` service never mounts: the API's
# own token (`policy.hcl`, `diagnos-sdk`) may only *read* this path, so a
# compromised API cannot swap the token for another account's. No
# placeholders — the path is the same for every deployment, because
# whoever reads it does not have the token yet (one deployment, one prefix,
# one token). If `OPENBAO_MOUNT`/`OPENBAO_PATH_PREFIX` change, change both
# policies with them.
# 🇧🇷 Política `diagnos-token-writer`: a única coisa que o token *de escrita*
# pode fazer — guardar, girar ou remover o token da conta de serviço do
# diagnos em `secret/diagnos/token` (`diagnos login --store openbao`, o
# serviço `login` em `../docker-compose.yml`). O `bootstrap.sh` o emite no
# volume `openbao-admin`, que o serviço `api` nunca monta: o token da
# própria API (`policy.hcl`, `diagnos-sdk`) só pode *ler* este caminho,
# então uma API comprometida não consegue trocar o token pelo de outra
# conta. Sem marcadores — o caminho é o mesmo em todo deployment, porque
# quem o lê ainda não tem o token (um deployment, um prefixo, um token). Se
# `OPENBAO_MOUNT`/`OPENBAO_PATH_PREFIX` mudarem, mude as duas políticas
# junto.

# 🇺🇸 The secret itself: `create`/`update` to store and rotate it, `read`
# because `diagnos logout` checks there is something before removing it.
# 🇧🇷 O segredo em si: `create`/`update` para guardar e girar, `read` porque
# o `diagnos logout` confere se há algo antes de remover.
path "secret/data/diagnos/token" {
  capabilities = ["create", "update", "read"]
}

# 🇺🇸 `diagnos logout` removes every version, not only the current one
# (`delete_metadata_and_all_versions`). A rotation needs no cleanup:
# `bootstrap.sh` sets `max-versions=1` on this path, so a rotated-out token
# does not stay readable in the version history.
# 🇧🇷 O `diagnos logout` remove todas as versões, não só a atual
# (`delete_metadata_and_all_versions`). Uma rotação não precisa de limpeza:
# o `bootstrap.sh` define `max-versions=1` neste caminho, então um token
# girado não continua legível no histórico de versões.
path "secret/metadata/diagnos/token" {
  capabilities = ["read", "delete"]
}
