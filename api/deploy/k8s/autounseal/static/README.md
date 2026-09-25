# OpenBao auto-unseal · Static key

🇺🇸 Wraps OpenBao's master key with a raw 32-byte AES-256-GCM-96 key you
generate and hold yourself — no cloud KMS, no second OpenBao/Vault.
Verified against
[openbao.org/docs/configuration/seal/static](https://openbao.org/docs/configuration/seal/static)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

🇧🇷 Envolve a master key do OpenBao com uma chave crua de 32 bytes
AES-256-GCM-96 que você gera e guarda por conta própria — sem KMS de
nuvem, sem um segundo OpenBao/Vault. Verificado contra
[openbao.org/docs/configuration/seal/static](https://openbao.org/docs/configuration/seal/static)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay
traz.

## Security warning · Aviso de segurança

🇺🇸 OpenBao's own documentation is blunt about this one: "carefully
evaluate use of Static Key Auto Unseal to see if its use meets the desired
security properties." A Kubernetes Secret is only as protected as your
cluster's etcd encryption and RBAC — unlike every other overlay here, this
one adds **no** separate trust boundary (no cloud KMS call, no second
OpenBao) between "read this Secret" and "read every workspace's saved
session." Use it only where an external, already-trusted secrets manager
exists to hand this key over, or for a genuinely disposable environment —
never as a default choice over `aws`/`gcp`/`azure`/`transit`.

🇧🇷 A própria documentação do OpenBao é direta sobre este: "avalie com
cuidado o uso do Static Key Auto Unseal para ver se atende às propriedades
de segurança desejadas." Um Secret do Kubernetes só está tão protegido
quanto a cifragem do etcd e o RBAC do seu cluster — diferente de todo outro
overlay aqui, este **não** soma nenhuma fronteira de confiança separada
(nenhuma chamada a KMS de nuvem, nenhum segundo OpenBao) entre "ler este
Secret" e "ler a sessão salva de todo workspace." Use só onde já existe um
gerenciador de segredos externo e confiável para entregar esta chave, ou
para um ambiente genuinamente descartável — nunca como escolha padrão
sobre `aws`/`gcp`/`azure`/`transit`.

## 1. Generate the key · Gerar a chave

```sh
openssl rand -base64 32
```

## 2. Apply · Aplicar

```sh
kubectl create secret generic openbao-static-seal \
  --from-literal=OPENBAO_STATIC_SEAL_CURRENT_KEY=<output of step 1> -n openbao
kubectl apply -k deploy/k8s/autounseal/static
```

## Rotation · Rotação

🇺🇸 Set `previous_key_id`/`previous_key` in `seal.hcl` (same `env://`
pattern, a second Secret key) alongside a new `current_key_id`/
`current_key` — OpenBao re-wraps with the new key going forward while
still reading anything sealed under the previous one. Remove the
`previous_*` pair only once you are certain nothing still needs it.

🇧🇷 Defina `previous_key_id`/`previous_key` em `seal.hcl` (mesmo padrão
`env://`, uma segunda chave no Secret) junto de um `current_key_id`/
`current_key` novos — o OpenBao volta a envolver com a chave nova daí em
diante, mas continua lendo o que foi selado sob a anterior. Remova o par
`previous_*` só quando tiver certeza de que nada mais precisa dele.

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 Set `OPENBAO_SEAL=static` in `deploy/compose/.env` and
`OPENBAO_STATIC_SEAL_CURRENT_KEY` to the same value from step 1.

🇧🇷 Defina `OPENBAO_SEAL=static` no `deploy/compose/.env` e
`OPENBAO_STATIC_SEAL_CURRENT_KEY` com o mesmo valor do passo 1.
