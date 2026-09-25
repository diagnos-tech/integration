# OpenBao auto-unseal · Chave estática

[English](README.md) · **Português (Brasil)**

Envolve a master key do OpenBao com uma chave crua de 32 bytes AES-256-GCM-96 que você gera e guarda por conta
própria — sem KMS de nuvem, sem um segundo OpenBao/Vault. Verificado contra
[openbao.org/docs/configuration/seal/static](https://openbao.org/docs/configuration/seal/static) (docs da v2.6.x)
— veja `seal.hcl` para o stanza exato que este overlay traz.

> [!WARNING]
> A própria documentação do OpenBao é direta sobre este: "avalie com cuidado o uso do Static Key Auto Unseal para
> ver se atende às propriedades de segurança desejadas." Um Secret do Kubernetes só está tão protegido quanto a
> cifragem do etcd e o RBAC do seu cluster — diferente de todo outro overlay aqui, este **não** soma nenhuma
> fronteira de confiança separada (nenhuma chamada a KMS de nuvem, nenhum segundo OpenBao) entre "ler este Secret" e
> "ler a sessão salva de todo workspace." Use só onde já existe um gerenciador de segredos externo e confiável para
> entregar esta chave, ou para um ambiente genuinamente descartável — nunca como escolha padrão sobre
> `aws`/`gcp`/`azure`/`transit`.

## 1. Gerar a chave

```sh
openssl rand -base64 32
```

## 2. Aplicar

```sh
kubectl create secret generic openbao-static-seal \
  --from-literal=OPENBAO_STATIC_SEAL_CURRENT_KEY=<output of step 1> -n openbao
kubectl apply -k deploy/k8s/autounseal/static
```

O `current_key_id` de `seal.hcl` traz `imgexam-static-v1` — mantenha o id da chave como está; ele é registrado pelo
OpenBao junto de cada segredo que sela, então renomeá-lo (mesmo com os pacotes tendo migrado de `imgexam` para
`diagnos`) quebraria o unseal de um OpenBao que já selou dado sob ele. Trate-o como um rótulo estável, não como um
nome de produto.

## Rotação

Defina `previous_key_id`/`previous_key` em `seal.hcl` (mesmo padrão `env://`, uma segunda chave no Secret) junto de
um `current_key_id`/`current_key` novos — o OpenBao volta a envolver com a chave nova daí em diante, mas continua
lendo o que foi selado sob a anterior. Remova o par `previous_*` só quando tiver certeza de que nada mais precisa
dele.

## Reaproveitado pelo Compose

Defina `OPENBAO_SEAL=static` no `deploy/compose/.env` e `OPENBAO_STATIC_SEAL_CURRENT_KEY` com o mesmo valor do
passo 1.
