# diagnos-api · Docker Compose

[English](README.md) · **Português (Brasil)**

Um único `docker compose up` para OpenBao + `diagnos-api`, montado para desenvolvimento local e staging. Para um
deployment de produção em Kubernetes, veja `../k8s/openbao` (o próprio OpenBao) e `../k8s` (a API) — este compose
troca algumas preocupações de produção (um seal de verdade apoiado em KMS por padrão, um cluster raft multi-nó) por
"um comando só, nada mais para rodar."

## Início rápido

```sh
cp .env.example .env
# edite .env: DIAGNOS_API_TOKEN, depois `diagnos status` para os dois ids
```

Gere o material de mTLS em `certs/` — a receita exata de `openssl` está na seção "Gerando uma CA e certificados com
openssl" de [`../../README.pt-BR.md`](../../README.pt-BR.md); esta stack de compose espera `certs/clients-ca.pem`,
`certs/server.pem`, `certs/server-key.pem`.

```sh
docker compose up
```

Primeira execução: `openbao` sobe selado e não inicializado, `openbao-bootstrap` inicializa, dessela (só para
`OPENBAO_SEAL=shamir` — todo outro valor se dessela sozinho), habilita o KV v2, escreve a política `diagnos-sdk` a
partir de `openbao/policy.hcl`, e emite o token restrito que `api` lê. `api` só sobe depois que esse bootstrap sai
com `0`.

## O que o bootstrap faz

`openbao/bootstrap.sh` roda uma vez como o serviço `openbao-bootstrap` (entrypoint `sh /bootstrap/bootstrap.sh` na
mesma imagem `openbao/openbao` — sem imagem extra para construir ou confiar) e é idempotente entre reinícios:
reconfere o status toda vez e pula o que já está feito, usando só `sh` POSIX mais `bao`/`grep`/`sed` (sem `jq`,
ausente naquela imagem).

1. Espera `openbao:8200` responder (qualquer status — selado conta).
2. `bao operator init -format=json` se ainda não inicializado; escreve a saída completa (chaves de recovery/unseal
   **e o root token**) no volume `openbao-state` em `0600` e imprime um aviso para movê-los para fora.
3. Dessela com as chaves salvas — só relevante para `OPENBAO_SEAL=shamir`, já que todo seal apoiado em KMS se
   dessela sozinho assim que o processo sobe.
4. Habilita o KV v2 em `secret` (idempotente — um segundo `enable` falhar com "already in use" é o caminho de
   sucesso).
5. Escreve a política `diagnos-sdk` a partir de `openbao/policy.hcl` com `__WORKSPACE_ID__`/`__ACCOUNT_ID__`
   substituídos a partir do `.env`.
6. Emite um token órfão e renovável restrito a essa política e escreve em `/state/openbao-token` (`0600`) — pulado
   se um token já ali ainda passa em `bao token lookup`.

> [!WARNING]
> **Só para staging, leia isto.** Com `OPENBAO_SEAL=shamir` (o padrão), o passo 3 só funciona porque o passo 2
> deixou as chaves de unseal no volume `openbao-state`, sem cifrar. É uma conveniência deliberada para um ambiente
> descartável — significa que qualquer um com acesso a esse volume Docker consegue desselar o OpenBao e ler toda
> sessão salva, sem precisar de credencial nenhuma do OpenBao. Não rode esta configuração em nada que importe; use
> `OPENBAO_SEAL=aws`/`gcp`/`azure`/`transit` (o `.env.example` tem as credenciais que cada um precisa) ou dessela na
> mão e mantenha as chaves de recovery totalmente fora desta máquina.

## `OPENBAO_TOKEN_FILE`

O serviço `api` nunca vê o token do OpenBao como valor de ambiente: o `openbao-bootstrap` o escreve em
`/state/openbao-token` (`0600`, com o uid 10001 da API) e o próprio SDK lê esse caminho —
`diagnos.Settings.from_env()` respeita `OPENBAO_TOKEN_FILE` sempre que `OPENBAO_TOKEN` não está definida. Nada nesta
stack põe o token na saída de `docker inspect` nem no ambiente de um processo.

## Desmontando

```sh
docker compose down        # mantém openbao-data/openbao-state
docker compose down -v     # destrói — veja os avisos dos volumes em docker-compose.yml
```
