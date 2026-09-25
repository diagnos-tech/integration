#!/bin/sh
# 🇺🇸 One-shot bootstrap for the Compose OpenBao: initialise (or resume),
# unseal when the seal is Shamir, enable KV v2, and issue the scoped token
# `diagnos-api` reads via `OPENBAO_TOKEN_FILE`. Runs once per `docker
# compose up` as the `openbao-bootstrap` service, using only POSIX `sh` and
# the binaries already in the `openbao/openbao` image (no `jq` — see the
# `_json_field`/`_json_array` helpers below) because that image is all this
# container has.
#
# STAGING-ONLY WARNING: with `OPENBAO_SEAL=shamir` this script keeps the
# unseal keys on the `openbao-state` volume so it can re-unseal on every
# `docker compose restart` without a human. That is a deliberate convenience
# for a throwaway environment, not a production posture — in production,
# either configure a real auto-unseal backend (`OPENBAO_SEAL=aws|gcp|azure|
# transit`, see `../k8s/autounseal/*/README.md`) or unseal by hand and keep
# the recovery keys off any machine that also holds the encrypted data.
#
# 🇧🇷 Bootstrap de execução única para o OpenBao do Compose: inicializa (ou
# retoma), dessela quando o seal é Shamir, habilita o KV v2 e emite o token
# restrito que o `diagnos-api` lê via `OPENBAO_TOKEN_FILE`. Roda uma vez por
# `docker compose up` como o serviço `openbao-bootstrap`, usando só `sh`
# POSIX e os binários que já estão na imagem `openbao/openbao` (sem `jq` —
# veja os helpers `_json_field`/`_json_array` abaixo) porque é só isso que
# este container tem.
#
# AVISO SÓ-PARA-STAGING: com `OPENBAO_SEAL=shamir` este script guarda as
# chaves de unseal no volume `openbao-state` para poder desselar de novo a
# cada `docker compose restart` sem humano. É uma conveniência deliberada
# para um ambiente descartável, não uma postura de produção — em produção,
# configure um backend de auto-unseal de verdade (`OPENBAO_SEAL=aws|gcp|
# azure|transit`, veja `../k8s/autounseal/*/README.md`) ou dessela na mão e
# mantenha as chaves de recovery fora de qualquer máquina que também guarde
# os dados cifrados.
set -eu

BAO_ADDR="${OPENBAO_ADDR:-http://openbao:8200}"
export BAO_ADDR
STATE_DIR="/state"
INIT_FILE="$STATE_DIR/openbao-init.json"
TOKEN_FILE="$STATE_DIR/openbao-token"
POLICY_NAME="diagnos-sdk"
POLICY_SRC="/bootstrap/policy.hcl"
POLICY_RENDERED="/tmp/diagnos-sdk-policy.hcl"

log() {
  # 🇺🇸 Every line bilingual, like every other file here — this is the one
  # place an operator actually reads this container's output.
  # 🇧🇷 Toda linha bilíngue, como todo outro arquivo aqui — é o único lugar
  # onde um operador de fato lê a saída deste container.
  printf '[openbao-bootstrap] %s\n' "$1"
}

# 🇺🇸 Pulls one `"key": "value"` scalar out of a `-format=json` blob with
# grep+sed instead of jq (not present in this image). Assumes the CLI's own
# pretty-printer, which puts each scalar field on its own line — true for
# every `bao`/`vault` JSON output this script parses.
# 🇧🇷 Extrai um escalar `"key": "value"` de um JSON de `-format=json` com
# grep+sed em vez de jq (ausente nesta imagem). Assume o pretty-printer da
# própria CLI, que põe cada campo escalar em sua própria linha — verdade
# para todo JSON de `bao`/`vault` que este script interpreta.
_json_field() {
  field="$1"
  file="$2"
  grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"$/\1/'
}

_json_bool() {
  field="$1"
  file="$2"
  grep -o "\"${field}\"[[:space:]]*:[[:space:]]*(true|false)" "$file" | head -n1 | sed -E 's/.*:[[:space:]]*//'
}

# 🇺🇸 Pulls every string out of a `"field": [ "a", "b", ... ]` array,
# one per line — used for `unseal_keys_b64`, which only Shamir populates.
# 🇧🇷 Extrai toda string de um array `"field": [ "a", "b", ... ]`, uma por
# linha — usado em `unseal_keys_b64`, que só o Shamir preenche.
_json_array() {
  field="$1"
  file="$2"
  sed -n "/\"${field}\"/,/\]/p" "$file" | grep -o '"[A-Za-z0-9+/=]\{20,\}"' | tr -d '"'
}

wait_for_openbao() {
  # 🇺🇸 `bao status` exits 0 unsealed, 2 sealed (uninitialised counts as
  # sealed) — both mean "reachable". Only exit 1 (or the process not being
  # up yet at all) means "keep waiting"; this loop must not require
  # unsealed, because unsealing is this very script's job.
  # 🇧🇷 `bao status` sai 0 desselado, 2 selado (não inicializado conta como
  # selado) — os dois significam "alcançável". Só o exit 1 (ou o processo
  # ainda nem estar de pé) significa "continue esperando"; este laço não
  # pode exigir desselado, porque desselar é o trabalho deste script.
  tries=0
  max_tries=60
  while [ "$tries" -lt "$max_tries" ]; do
    ec=0
    bao status >/tmp/status.out 2>&1 || ec=$?
    if [ "$ec" -eq 0 ] || [ "$ec" -eq 2 ]; then
      return 0
    fi
    tries=$((tries + 1))
    sleep 2
  done
  log "🇺🇸 timed out waiting for $BAO_ADDR to answer · 🇧🇷 tempo esgotado esperando $BAO_ADDR responder"
  cat /tmp/status.out || true
  exit 1
}

is_sealed() {
  bao status -format=json >/tmp/status.json 2>/dev/null || true
  [ "$(_json_bool sealed /tmp/status.json)" = "true" ]
}

is_initialized() {
  bao status -format=json >/tmp/status.json 2>/dev/null || true
  [ "$(_json_bool initialized /tmp/status.json)" = "true" ]
}

unseal_with_saved_keys() {
  # 🇺🇸 Shamir-only path: re-unseal a restarted `openbao` container using
  # the keys this same script saved to `$INIT_FILE` on first boot. Nothing
  # to do for an auto-unseal backend — the KMS/Transit call happens inside
  # `bao` itself as soon as the process starts, before this script even
  # gets to check.
  # 🇧🇷 Caminho só-Shamir: dessela de novo um container `openbao` reiniciado
  # usando as chaves que este mesmo script salvou em `$INIT_FILE` na
  # primeira subida. Nada a fazer para um backend de auto-unseal — a
  # chamada ao KMS/Transit acontece dentro do próprio `bao` assim que o
  # processo sobe, antes deste script sequer checar.
  if [ ! -f "$INIT_FILE" ]; then
    log "🇺🇸 sealed, but no saved keys at $INIT_FILE — this is expected right after a fresh init with an auto-unseal backend (it should already be unsealing itself); for Shamir it means the state volume was lost and someone must unseal by hand. · 🇧🇷 selado, mas sem chaves salvas em $INIT_FILE — isso é esperado logo após um init novo com backend de auto-unseal (ele já deveria estar se desselando sozinho); para Shamir significa que o volume de estado se perdeu e alguém precisa desselar na mão."
    return 0
  fi
  threshold="$(_json_field unseal_threshold "$INIT_FILE")"
  [ -n "$threshold" ] || threshold="$(_json_field recovery_threshold "$INIT_FILE")"
  count=0
  for key in $(_json_array unseal_keys_b64 "$INIT_FILE"); do
    [ -n "$threshold" ] && [ "$count" -ge "$threshold" ] && break
    bao operator unseal "$key" >/dev/null
    count=$((count + 1))
  done
}

ensure_kv_v2() {
  # 🇺🇸 `bao secrets enable` has no `-force`/idempotent flag; the second run
  # always fails with "path is already in use" on stderr, which is exactly
  # the success case here, so it is matched and swallowed instead of
  # treated as an error.
  # 🇧🇷 `bao secrets enable` não tem flag `-force`/idempotente; a segunda
  # execução sempre falha com "path is already in use" no stderr, que é
  # exatamente o caso de sucesso aqui, então é reconhecido e engolido em
  # vez de tratado como erro.
  if ! bao secrets enable -path=secret kv-v2 >/tmp/enable.out 2>&1; then
    if ! grep -q "already in use" /tmp/enable.out; then
      cat /tmp/enable.out
      exit 1
    fi
  fi
}

write_policy() {
  : "${DIAGNOS_WORKSPACE_ID:?DIAGNOS_WORKSPACE_ID must be set in .env — run \`diagnos status\` with the token this deployment will use to find it. / precisa estar no .env — rode \`diagnos status\` com o token que este deployment vai usar para descobrir.}"
  : "${DIAGNOS_ACCOUNT_ID:?DIAGNOS_ACCOUNT_ID must be set in .env — same \`diagnos status\` output. / precisa estar no .env — mesma saída de \`diagnos status\`.}"
  sed -e "s/__WORKSPACE_ID__/${DIAGNOS_WORKSPACE_ID}/g" -e "s/__ACCOUNT_ID__/${DIAGNOS_ACCOUNT_ID}/g" "$POLICY_SRC" >"$POLICY_RENDERED"
  bao policy write "$POLICY_NAME" "$POLICY_RENDERED" >/dev/null
}

issue_token() {
  bao token create -orphan -policy="$POLICY_NAME" -display-name=diagnos-api -renewable=true -format=json >/tmp/token.json
  client_token="$(_json_field client_token /tmp/token.json)"
  if [ -z "$client_token" ]; then
    log "🇺🇸 could not parse client_token from bao token create output · 🇧🇷 não consegui extrair client_token da saída de bao token create"
    cat /tmp/token.json
    exit 1
  fi
  printf '%s' "$client_token" >"$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  # 🇺🇸 The API container reads this file as uid 10001 (`apps/api/Dockerfile`);
  # in Compose this script runs as root and hands the file over. Under
  # Kubernetes it runs as the `openbao` user via `kubectl exec`, the chown
  # is not permitted, and the operator copies the token into a Secret
  # instead (`../../k8s/openbao/bootstrap-configmap.yaml`) — hence the
  # soft failure.
  # 🇧🇷 O container da API lê este arquivo como uid 10001 (`apps/api/Dockerfile`);
  # no Compose este script roda como root e entrega o arquivo. No
  # Kubernetes ele roda como o usuário `openbao` via `kubectl exec`, o chown
  # não é permitido, e o operador copia o token para um Secret
  # (`../../k8s/openbao/bootstrap-configmap.yaml`) — daí a falha suave.
  chown "${DIAGNOS_API_UID:-10001}" "$TOKEN_FILE" 2>/dev/null \
    || log "🇺🇸 could not chown $TOKEN_FILE to uid ${DIAGNOS_API_UID:-10001} (expected under Kubernetes) · 🇧🇷 não consegui fazer chown de $TOKEN_FILE para o uid ${DIAGNOS_API_UID:-10001} (esperado no Kubernetes)"
}

token_is_valid() {
  [ -f "$TOKEN_FILE" ] || return 1
  BAO_TOKEN="$(cat "$TOKEN_FILE")" bao token lookup >/dev/null 2>&1
}

main() {
  mkdir -p "$STATE_DIR"
  wait_for_openbao

  root_token="${BAO_ROOT_TOKEN_OVERRIDE:-}"

  if ! is_initialized; then
    log "🇺🇸 not initialized — running \`bao operator init\` (once, ever, for this raft volume) · 🇧🇷 não inicializado — rodando \`bao operator init\` (uma vez, para sempre, para este volume raft)"
    bao operator init -format=json >"$INIT_FILE"
    chmod 600 "$INIT_FILE"
    root_token="$(_json_field root_token "$INIT_FILE")"
    log "############################################################"
    log "🇺🇸 SECURITY: $INIT_FILE now holds the recovery/unseal keys AND"
    log "the root token, in cleartext, on the openbao-state volume. Copy"
    log "them to an offline secret store NOW and delete them from this"
    log "volume — anyone who can read this file owns this OpenBao."
    log "🇧🇷 SEGURANÇA: $INIT_FILE agora tem as chaves de recovery/unseal E"
    log "o root token, em texto claro, no volume openbao-state. Copie"
    log "para um cofre de segredos offline AGORA e apague deste volume —"
    log "quem ler este arquivo é dono deste OpenBao."
    log "############################################################"
  fi

  if is_sealed; then
    unseal_with_saved_keys
  fi

  if token_is_valid; then
    log "🇺🇸 existing $TOKEN_FILE still resolves via \`bao token lookup\` — keeping it, no root privileges needed. · 🇧🇷 $TOKEN_FILE existente ainda resolve via \`bao token lookup\` — mantendo, sem precisar de privilégio de root."
    exit 0
  fi

  if [ -z "$root_token" ] && [ -f "$INIT_FILE" ]; then
    root_token="$(_json_field root_token "$INIT_FILE")"
  fi
  if [ -z "$root_token" ]; then
    log "🇺🇸 no usable token at $TOKEN_FILE and no root token available (no fresh init this run, $INIT_FILE absent or already cleaned up). Set BAO_ROOT_TOKEN_OVERRIDE in .env to a privileged token for one run to reissue it. TODO(gustavo): a real recovery flow (recovery-key-based root generation) is out of scope for a staging bootstrap script."
    log "🇧🇷 nenhum token utilizável em $TOKEN_FILE e nenhum root token disponível (sem init novo nesta execução, $INIT_FILE ausente ou já limpo). Defina BAO_ROOT_TOKEN_OVERRIDE no .env com um token privilegiado por uma execução para reemitir. TODO(gustavo): um fluxo de recovery de verdade (geração de root a partir das chaves de recovery) está fora do escopo de um script de bootstrap de staging."
    exit 1
  fi

  BAO_TOKEN="$root_token"
  export BAO_TOKEN
  ensure_kv_v2
  write_policy
  issue_token
  log "🇺🇸 wrote scoped token to $TOKEN_FILE (policy: $POLICY_NAME) · 🇧🇷 token restrito escrito em $TOKEN_FILE (política: $POLICY_NAME)"
}

main "$@"
