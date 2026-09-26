# Início rápido

[English](quickstart.md) · **Português (Brasil)**

De um token de service account até o primeiro paciente e o primeiro arquivo cifrados, em uns cinco minutos. Todo
byte de dado clínico abaixo é cifrado dentro do seu próprio processo antes de tocar a rede; o cofre só guarda
ciphertext.

## Antes de começar

| Você precisa de | De onde vem |
|---|---|
| Python 3.11, 3.12 ou 3.13 | [python.org](https://www.python.org/downloads/) ou o seu gerenciador de pacotes |
| Um token de service account (`apikey-…`) | Um admin do workspace cria no app web do diagnos |
| Alguém que possa aprovar um enrollment | Um admin do workspace, com o app web aberto |

> [!NOTE]
> O token identifica *qual* service account está pedindo. Sozinho, ele não desbloqueia nada: a primeira execução
> imprime um link e um código de 6 dígitos que um admin aprova — veja [Autenticação](authentication.pt-BR.md) para
> entender por quê.

## 1. Instale

```sh
pip install diagnos          # o SDK
pipx install diagnos-cli     # opcional: o comando `diagnos`
```

Até o primeiro release no PyPI, instale do código-fonte — [Instalação](install.pt-BR.md) tem os comandos exatos,
inclusive o toolchain Rust que o build do fonte precisa.

## 2. Entregue o token ao processo

```sh
export DIAGNOS_API_TOKEN="apikey-…"
```

O SDK o lê do ambiente; a CLI também aceita `--token` para uma única invocação. Nada o imprime de volta: todo
`repr` do SDK é redigido.

## 3. Faça o enrollment e grave o primeiro paciente

```python
from diagnos import Diagnos

with Diagnos() as vault:  # imprime um link de aprovação e um código de 6 dígitos, e espera
    print("workspace:", vault.workspace_id)
    print("grupos:", vault.security_groups)

    group = vault.security_groups[0]  # os security groups que o admin concedeu
    patient = vault.patients.create(
        {"legal_name": "Maria da Silva", "display_name": "Maria", "birth_date": "1990-01-31"},
        security_group=group,
        tags=["retorno"],
    )
    print("criado", patient.id, "versão", patient.version_id)
```

Enquanto `Diagnos()` espera, abra o link impresso no app web, confira que a máquina descrita ali é a sua, digite o
código e escolha os security groups que este processo pode ler. O bloco continua no instante em que você aprova.

`security_groups` é a lista que o admin concedeu; um documento pertence a exatamente um deles. Tudo no registro —
nomes, data de nascimento — é selado sob uma chave nova antes de sair; o cofre só fica sabendo que existe um
paciente naquele grupo.

## 4. Leia de volta

```python
with Diagnos() as vault:
    for row in vault.patients.list():  # os nomes vêm de um resumo selado: nenhuma versão é baixada
        print(row.id, row.summary.display_name if row.summary else "—")

    same = vault.patients.get(patient.id)  # baixa e decifra a versão mais nova
    print(same.record.legal_name, same.tags)
```

> [!TIP]
> Cada `Diagnos()` acima faz enrollment de novo, porque uma sessão vive só na memória do processo que a conquistou.
> Em código de verdade, mantenha um `vault` pela vida inteira do processo — e leia [Sessões](sessions.pt-BR.md)
> antes de rodar num servidor que reinicia sem uma pessoa.

## 5. Suba e baixe um arquivo

```python
with Diagnos() as vault:
    drive = vault.drives.drive(vault.security_groups[0])
    node = drive.upload("scans/IM-0001.dcm")  # chave própria; nome e conteúdo selados
    print(node.node_id, drive.name_of(node), node.mime_type, node.size)

    data = vault.drives.download(node.node_id)  # bytes na RAM, decifrados
    vault.drives.download(node.node_id, "copia-de-IM-0001.dcm")  # ou direto para um arquivo
```

## 6. O mesmo pelo terminal

```sh
diagnos login                                   # faz enrollment; imprime o que foi concedido
diagnos patients create --group sg_oncology --legal-name "Maria da Silva" --display-name Maria
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology scans/IM-0001.dcm
```

Cada invocação do `diagnos` é um processo próprio, então cada uma faz enrollment a menos que o OpenBao esteja
configurado — o [guia da CLI](cli.pt-BR.md) explica como rodá-la em scripts e cron.

## Para onde ir agora

| Para… | Leia |
|---|---|
| entender workspaces, grupos, versões e nós | [Conceitos](concepts.pt-BR.md) |
| ler, atualizar, arquivar e apagar com segurança | [Pacientes](patients.pt-BR.md) · [Exames](exams.pt-BR.md) · [Arquivos](files.pt-BR.md) |
| rodar num servidor sem uma pessoa | [Sessões e auto-unseal com OpenBao](sessions.pt-BR.md) |
| tratar toda falha | [Erros](errors.pt-BR.md) |
| chamar por HTTP em vez disso | [Guia da API REST](api.pt-BR.md) |
| saber exatamente o que o cofre consegue ver | [Modelo de segurança](security.pt-BR.md) |
