# 🇺🇸 OpenBao server configuration for the Compose stack. Mounted read-only
# into the container by `docker-compose.yml`; `openbao/<seal>/seal.hcl`
# (selected by `OPENBAO_SEAL` in `.env`) is bind-mounted into the *same*
# directory so `bao server -config=/openbao/config` loads both files.
# 🇧🇷 Configuração do servidor OpenBao para a stack Compose. Montada
# somente-leitura no container por `docker-compose.yml`; o
# `openbao/<seal>/seal.hcl` (escolhido por `OPENBAO_SEAL` no `.env`) é
# montado no *mesmo* diretório, então `bao server -config=/openbao/config`
# carrega os dois arquivos.

# 🇺🇸 No TLS on this listener: inside the Compose network only `api` and
# `openbao-bootstrap` ever dial `openbao:8200`, and neither leaves the
# Docker bridge. Putting TLS in front means terminating it at a reverse
# proxy (Caddy/Traefik/nginx) added as another Compose service in front of
# this port, or — for a deployment that must encrypt this hop too — adding
# `tls_cert_file`/`tls_key_file` here and switching the healthcheck and
# `OPENBAO_ADDR` to `https://`. Kubernetes' base (`../k8s/openbao`) makes
# the same call for the same reason (ClusterIP, not exposed outside the
# cluster network).
# 🇧🇷 Sem TLS neste listener: dentro da rede do Compose só `api` e
# `openbao-bootstrap` discam `openbao:8200`, e nenhum dos dois sai da bridge
# do Docker. Colocar TLS na frente significa terminar num proxy reverso
# (Caddy/Traefik/nginx) somado como outro serviço do Compose na frente
# desta porta, ou — para um deployment que precise cifrar este trecho
# também — somar `tls_cert_file`/`tls_key_file` aqui e trocar o healthcheck
# e `OPENBAO_ADDR` para `https://`. A base do Kubernetes (`../k8s/openbao`)
# faz a mesma escolha pelo mesmo motivo (ClusterIP, não exposto fora da
# rede do cluster).
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# 🇺🇸 Integrated storage (raft): a named volume (`openbao-data` in
# `docker-compose.yml`) survives `docker compose down` but not `down -v`,
# which is the point — losing this volume without a copy of the recovery
# keys means the encrypted data is unrecoverable by design, not a bug.
# `node_id` is left unset on purpose: OpenBao generates one and persists it
# under `path` on first boot, which is exactly what a single fixed node
# needs and avoids duplicating the pod-name logic Kubernetes' StatefulSet
# already provides.
# 🇧🇷 Armazenamento integrado (raft): um volume nomeado (`openbao-data` em
# `docker-compose.yml`) sobrevive a `docker compose down`, mas não a
# `down -v` — de propósito: perder este volume sem uma cópia das chaves de
# recovery torna os dados cifrados irrecuperáveis por desenho, não é bug.
# `node_id` fica de propósito sem definir: o OpenBao gera um e persiste sob
# `path` na primeira subida, exatamente o que um único nó fixo precisa, sem
# duplicar a lógica de nome de pod que o StatefulSet do Kubernetes já dá.
storage "raft" {
  path = "/openbao/data"
}

# 🇺🇸 `false`: this is what makes `cap_add: [IPC_LOCK]` in
# `docker-compose.yml` load-bearing — without it OpenBao refuses to start
# rather than run with key material swappable to disk (the same reasoning
# as `DIAGNOS_MEMORY_LOCK` on the API side, `../k8s/configmap.yaml`).
# 🇧🇷 `false`: é isto que torna `cap_add: [IPC_LOCK]` em
# `docker-compose.yml` indispensável — sem ele o OpenBao se recusa a subir
# em vez de rodar com material de chave que pode ir para o disco (mesmo
# raciocínio do `DIAGNOS_MEMORY_LOCK` do lado da API, `../k8s/configmap.yaml`).
disable_mlock = false

# 🇺🇸 No web UI: one more surface a client-certificate-only deployment does
# not need to reason about.
# 🇧🇷 Sem UI web: mais uma superfície que um deployment só-de-certificado-
# cliente não precisa considerar.
ui = false

# 🇺🇸 Both point at the Compose service name — `openbao-bootstrap` and
# `api` resolve it through the same Docker DNS, and raft's own cluster
# traffic (port 8201, never published to the host) needs an address to
# advertise even with a single node.
# 🇧🇷 Os dois apontam para o nome do serviço no Compose — `openbao-bootstrap`
# e `api` resolvem pelo mesmo DNS do Docker, e o tráfego de cluster do raft
# (porta 8201, nunca publicada no host) precisa de um endereço para
# anunciar mesmo com um único nó.
api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"
