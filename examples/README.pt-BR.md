# Exemplos

[English](README.md) · **Português (Brasil)**

Programas pequenos e completos para o SDK Python, um por pasta: um `main.py` que se lê em um minuto e roda como está.
Usam o mesmo fluxo de credencial do código de produção — nada é falsificado, nada é pulado.

| Pasta | Mostra |
|---|---|
| [`01-quickstart`](01-quickstart/README.pt-BR.md) | credencial → enrollment → primeira chamada |
| [`02-upload-file`](02-upload-file/README.pt-BR.md) | um arquivo no drive, listado e baixado de volta |
| [`03-patients`](03-patients/README.pt-BR.md) | criar, listar e ler pacientes |
| [`04-exams`](04-exams/README.pt-BR.md) | um exame com laudo e um arquivo anexado a ele |
| [`05-error-handling`](05-error-handling/README.pt-BR.md) | toda falha que o SDK lança, e o que fazer com ela |
| [`06-lock-session`](06-lock-session/README.pt-BR.md) | encerrar a sessão de propósito com `lock()` |

Não há exemplo de async (o SDK é síncrono), de criar link de compartilhamento (o SDK não tem chamada para isso; os
links são feitos no app web) nem do visualizador público (uma rota de quem recebe um link, não do SDK).

## Antes de rodar qualquer um

```sh
pip install "diagnos[sdk]"
export DIAGNOS_CREDENTIAL='svc_<32 hex>@<workspace_id>.diagnos.health:<chave de 43 caracteres>'
```

- **A credencial** é a linha que um admin do workspace copia ao criar uma conta de serviço (Configurações → Contas
  de serviço). `DIAGNOS_CREDENTIALS_FILE` (o JSON baixado) e `~/.config/diagnos/credentials.json` também servem. O
  antigo `DIAGNOS_API_TOKEN` (`apikey-…`) ainda funciona até **2027-04-15**, com aviso de depreciação — veja
  [Autenticação](../docs/guides/authentication.pt-BR.md).
- **Quem aprova.** A primeira chamada imprime um link e um código de 6 dígitos no `stderr`; um admin abre o link no
  app web, digita o código e escolhe os security groups que o processo pode ler. O programa continua sozinho.
- **Um grupo.** Os exemplos usam o primeiro grupo concedido; defina `DIAGNOS_GROUP` para escolher outro.

Depois, na pasta de um exemplo:

```sh
python main.py
```

## Contra uma pilha local

`DIAGNOS_VAULT_URL` aponta o SDK para outro cofre; o padrão é `https://vault.diagnos.health`. Aponte-o para uma
pilha local ou de homologação para testar os exemplos que gravam dados:

```sh
export DIAGNOS_VAULT_URL=http://127.0.0.1:8787
```

> [!WARNING]
> Os exemplos 02, 03 e 04 **criam** pacientes, exames e arquivos. Rode-os num workspace descartável, nunca contra
> dados clínicos reais.

## Checagens

`make lint` e `make types` cobrem esta pasta: ruff, a regra de docstring bilíngue e `mypy --strict`, um exemplo por
vez (cada um é um `main.py`). `make test` roda todos de ponta a ponta contra o duplo de cofre em memória do
SDK. Um `example.json` ao lado de um `main.py` é lido pelo harness ponta a ponta (o comando, um prazo, os documentos
que ele deve achar criados, as linhas que deve imprimir).
