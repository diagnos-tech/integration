# diagnos-api · Docker Compose

[English](README.md) · **Português (Brasil)**

Um único `docker compose up` para OpenBao + `diagnos-api`, montado para desenvolvimento local e staging. Para um
deployment de produção em Kubernetes, veja `../k8s/openbao` (o próprio OpenBao) e `../k8s` (a API) — este compose
troca algumas preocupações de produção (um seal de verdade apoiado em KMS por padrão, um cluster raft multi-nó) por
"um comando só, nada mais para rodar."

## Início rápido

```sh
cp .env.example .env
# edite .env: o workspace e o key id do token (svc_…) — o `diagnos whoami` imprime os dois
```

Gere o material de mTLS em `certs/` com a receita de `openssl` do
[guia da API REST](../../../../docs/guides/api.pt-BR.md#certificados); esta stack de compose espera
`certs/clients-ca.pem`, `certs/server.pem` (o `tls.pem` da receita) e `certs/server-key.pem` (o `tls-key.pem` dela).

```sh
docker compose --profile login run --rm login   # cole o token (dgn_sk1_…): ele vai para o OpenBao, nunca para o .env
docker compose up
```

Primeira execução: `openbao` sobe selado e não inicializado, `openbao-bootstrap` inicializa, dessela (só para
`OPENBAO_SEAL=shamir` — todo outro valor se dessela sozinho), habilita o KV v2, escreve as políticas `diagnos-sdk` e
`diagnos-token-writer`, e emite os dois tokens restritos. `login` (e `api`) só sobem depois que esse bootstrap sai com
`0`; o `login` confere o CRC do token, prova-o contra o cofre (`whoami`) e o guarda. A `api` o lê na subida.

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
   substituídos a partir do `.env` (a sessão salva, e *leitura* de `secret/diagnos/token`), e a política
   `diagnos-token-writer` a partir de `openbao/token-writer-policy.hcl` (guardar, girar ou remover
   `secret/diagnos/token`, nada mais); mantém uma versão só desse caminho (`max-versions=1`), então um token girado
   não continua legível.
6. Emite um token órfão e renovável restrito a `diagnos-sdk` e escreve em `/state/openbao-token` (`0600`), e um
   restrito a `diagnos-token-writer` em `/admin/openbao-token-writer` (o volume `openbao-admin`, montado só pelo
   `login`) — cada um pulado se o que já está ali ainda passa em `bao token lookup`. Um token de escrita ausente sem
   root token só registra no log como reemiti-lo: a API sobe mesmo assim.

> [!WARNING]
> **Só para staging, leia isto.** Com `OPENBAO_SEAL=shamir` (o padrão), o passo 3 só funciona porque o passo 2
> deixou as chaves de unseal no volume `openbao-state`, sem cifrar. É uma conveniência deliberada para um ambiente
> descartável — significa que qualquer um com acesso a esse volume Docker consegue desselar o OpenBao e ler toda
> sessão salva, sem precisar de credencial nenhuma do OpenBao. Não rode esta configuração em nada que importe; use
> `OPENBAO_SEAL=aws`/`gcp`/`azure`/`transit` (o `.env.example` tem as credenciais que cada um precisa) ou dessela na
> mão e mantenha as chaves de recovery totalmente fora desta máquina.

## O token do diagnos

O token da conta de serviço nunca vai no `.env`. O `docker compose --profile login run --rm login` roda
`diagnos login --store openbao` na imagem da linha de comando: entrada oculta, o CRC conferido antes de qualquer rede,
`whoami` contra o cofre (uma sessão só abre quando as assinaturas Ed25519 e ML-DSA-65 verificam), depois uma escrita
em `secret/diagnos/token` com o token de escrita. Rode de novo para girar o token, depois
`docker compose restart api`. O token do OpenBao da própria API só pode *ler* esse caminho, então uma API
comprometida não consegue trocar o token nem apagá-lo.

**Atualizando do token `apikey-`:** apague `DIAGNOS_API_TOKEN` do `.env`, defina `DIAGNOS_ACCOUNT_ID` com o key id do
token novo, defina `BAO_ROOT_TOKEN_OVERRIDE` no `.env` para um `docker compose run --rm openbao-bootstrap` (ele grava
as políticas novas e emite o token de escrita; remova-o logo depois), e então rode o serviço `login` como acima.

## `OPENBAO_TOKEN_FILE`

O serviço `api` nunca vê o token do OpenBao como valor de ambiente: o `openbao-bootstrap` o escreve em
`/state/openbao-token` (`0600`, com o uid 10001 da API) e o próprio SDK lê esse caminho —
`diagnos.Settings.from_env()` respeita `OPENBAO_TOKEN_FILE` sempre que `OPENBAO_TOKEN` não está definida. Nada nesta
stack põe o token na saída de `docker inspect` nem no ambiente de um processo. O serviço `login` lê o token de escrita
do mesmo jeito, de `/admin/openbao-token-writer`.

## Desmontando

```sh
docker compose down        # mantém openbao-data/openbao-state/openbao-admin
docker compose down -v     # destrói — veja os avisos dos volumes em docker-compose.yml
```
