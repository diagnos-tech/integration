# OpenBao server configuration for the Compose stack. Mounted read-only into the container by `docker-compose.yml`;
# `openbao/<seal>/seal.hcl` (selected by `OPENBAO_SEAL` in `.env`) is bind-mounted into the *same* directory so
# `bao server -config=/openbao/config` loads both files.

# No TLS on this listener: inside the Compose network only `api` and `openbao-bootstrap` ever dial `openbao:8200`, and
# neither leaves the Docker bridge. Putting TLS in front means terminating it at a reverse proxy (Caddy/Traefik/nginx)
# added as another Compose service in front of this port, or — for a deployment that must encrypt this hop too — adding
# `tls_cert_file`/`tls_key_file` here and switching the healthcheck and `OPENBAO_ADDR` to `https://`. Kubernetes' base
# (`../k8s/openbao`) makes the same call for the same reason (ClusterIP, not exposed outside the cluster network).
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# Integrated storage (raft): a named volume (`openbao-data` in `docker-compose.yml`) survives `docker compose down` but
# not `down -v`, which is the point — losing this volume without a copy of the recovery keys means the encrypted data is
# unrecoverable by design, not a bug. `node_id` is left unset on purpose: OpenBao generates one and persists it under
# `path` on first boot, which is exactly what a single fixed node needs and avoids duplicating the pod-name logic
# Kubernetes' StatefulSet already provides.
storage "raft" {
  path = "/openbao/data"
}

# `false`: this is what makes `cap_add: [IPC_LOCK]` in `docker-compose.yml` load-bearing — without it OpenBao refuses to
# start rather than run with key material swappable to disk (the same reasoning as `DIAGNOS_MEMORY_LOCK` on the API
# side, `../k8s/configmap.yaml`).
disable_mlock = false

# No web UI: one more surface a client-certificate-only deployment does not need to reason about.
ui = false

# Both point at the Compose service name — `openbao-bootstrap` and `api` resolve it through the same Docker DNS, and
# raft's own cluster traffic (port 8201, never published to the host) needs an address to advertise even with a single
# node.
api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"
