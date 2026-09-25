# 🇺🇸 OpenBao server configuration for the Kubernetes base. Same content
# philosophy as `../../compose/openbao/config.hcl` (see that file's
# comments for the full reasoning on each setting) — this is the source
# `kustomization.yaml`'s `configMapGenerator` turns into the `openbao-config`
# ConfigMap; every `autounseal/<provider>` overlay merges its own
# `seal.hcl` key into that same ConfigMap so `bao server
# -config=/openbao/config` (a directory, `statefulset.yaml`) loads both.
# 🇧🇷 Configuração do servidor OpenBao para a base do Kubernetes. Mesma
# filosofia de conteúdo de `../../compose/openbao/config.hcl` (veja os
# comentários daquele arquivo para o raciocínio completo de cada
# configuração) — este é o fonte que o `configMapGenerator` do
# `kustomization.yaml` transforma no ConfigMap `openbao-config`; todo
# overlay `autounseal/<provedor>` funde sua própria chave `seal.hcl` nesse
# mesmo ConfigMap, então `bao server -config=/openbao/config` (um
# diretório, `statefulset.yaml`) carrega os dois.

# 🇺🇸 No TLS: the `openbao` Service is ClusterIP-only (`service.yaml`),
# reachable only from inside the cluster network, and only `diagnos-api`
# and an operator's `kubectl exec` ever dial it. A cluster that must
# encrypt in-mesh traffic terminates it at the service-mesh layer
# (mTLS sidecar) rather than here, to avoid every OpenBao config carrying
# its own certificate rotation story.
# 🇧🇷 Sem TLS: o Service `openbao` é só ClusterIP (`service.yaml`),
# alcançável só de dentro da rede do cluster, e só `diagnos-api` e um
# `kubectl exec` de operador o discam. Um cluster que precise cifrar
# tráfego dentro da malha termina isso na camada de service mesh (sidecar
# mTLS) em vez de aqui, para nenhuma config do OpenBao carregar sua própria
# história de rotação de certificado.
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# 🇺🇸 `path` is the StatefulSet's `volumeClaimTemplates` mount
# (`statefulset.yaml`) — one PVC per replica, and this base ships exactly
# one replica. `node_id` is left unset for the same reason as the compose
# config: OpenBao persists a generated one under `path` on first boot.
# 🇧🇷 `path` é o mount do `volumeClaimTemplates` do StatefulSet
# (`statefulset.yaml`) — um PVC por réplica, e esta base sobe exatamente uma
# réplica. `node_id` fica sem definir pelo mesmo motivo da config do
# compose: o OpenBao persiste um gerado sob `path` na primeira subida.
storage "raft" {
  path = "/openbao/data"
}

# 🇺🇸 `false`: `statefulset.yaml`'s `capabilities.add: [IPC_LOCK]` is what
# makes this possible under `readOnlyRootFilesystem` + non-root — see that
# file's comment for the full chain.
# 🇧🇷 `false`: o `capabilities.add: [IPC_LOCK]` do `statefulset.yaml` é o
# que torna isto possível sob `readOnlyRootFilesystem` + não-root — veja o
# comentário daquele arquivo para a cadeia completa.
disable_mlock = false

ui = false

# 🇺🇸 The Service name resolves inside the `openbao` namespace without a
# fully-qualified `.svc.cluster.local` suffix, matching what
# `../deployment.yaml`'s `OPENBAO_ADDR` (`http://openbao.openbao.svc:8200`)
# already assumes from the API's namespace.
# 🇧🇷 O nome do Service resolve dentro do namespace `openbao` sem o sufixo
# completo `.svc.cluster.local`, batendo com o que o `OPENBAO_ADDR`
# (`http://openbao.openbao.svc:8200`) do `../deployment.yaml` já assume a
# partir do namespace da API.
api_addr     = "http://openbao.openbao.svc:8200"
cluster_addr = "http://openbao.openbao.svc:8201"
