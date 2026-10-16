# Início rápido

[English](quickstart.md) · **Português (Brasil)**

De um token de conta de serviço até o primeiro paciente e o primeiro arquivo cifrados, em uns cinco minutos. Todo
byte de dado clínico abaixo é cifrado dentro do seu próprio processo antes de tocar a rede; o cofre só guarda
ciphertext.

## Antes de começar

| Você precisa de | De onde vem |
|---|---|
| Python 3.11, 3.12 ou 3.13 | [python.org](https://www.python.org/downloads/) ou o seu gerenciador de pacotes |
| Um token de conta de serviço (`dgn_sk1_…`) | Um admin do workspace cria no app web do diagnos (*Configurações → Contas de serviço*), escolhendo os security groups, e o copia uma vez |

> [!NOTE]
> O token é a identidade *e* a chave: não há etapa de aprovação, nem link, nem código. Por isso ele aparece uma vez e
> o lugar dele é o chaveiro do sistema, o OpenBao ou um cofre de segredos — nunca um arquivo no seu repositório. Veja
> [Autenticação](authentication.pt-BR.md).

## 1. Instale

```sh
pip install "diagnos[sdk]"        # o SDK
uv tool install "diagnos[cli]"    # opcional: o comando `diagnos` completo
```

Até o primeiro release no PyPI, instale do código-fonte — [Instalação](install.pt-BR.md) tem os comandos exatos,
inclusive o toolchain Rust que o build do fonte precisa.

## 2. Entregue o token ao processo

```sh
diagnos login                     # cole uma vez: conferido, provado, guardado no chaveiro do sistema
```

Sem a CLI — em CI, ou num container — ponha-o no ambiente, direto do seu cofre de segredos:

```sh
export DIAGNOS_TOKEN="dgn_sk1_…"
```

O SDK o acha em qualquer um dos dois lugares, confere o CRC (um token cortado falha aqui mesmo, dizendo isso) e move
a semente para o enclave em Rust, onde toda chave é derivada e toda requisição é assinada. Nada o imprime de volta:
todo `repr` do SDK mostra só a identidade. O antigo `DIAGNOS_API_TOKEN` ainda funciona até 2027-04-15, com aviso —
veja [Autenticação](authentication.pt-BR.md#o-token-legado-apikey-).

## 3. Abra uma sessão e grave o primeiro paciente

```python
from diagnos import Diagnos

with Diagnos() as vault:  # uma requisição assinada abre a sessão — sem prompt
    print("workspace:", vault.workspace_id)
    print("grupos:", vault.security_groups)

    group = vault.security_groups[0]  # os security groups que o admin escolheu para o token
    patient = vault.patients.create(
        {"legal_name": "Maria da Silva", "display_name": "Maria", "birth_date": "1990-01-31"},
        security_group=group,
        tags=["retorno"],
    )
    print("criado", patient.id, "versão", patient.version_id)
```

`security_groups` é a lista que o admin escolheu para o token; um documento pertence a exatamente um deles. Tudo no registro —
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
> Cada `Diagnos()` acima abre uma sessão nova, porque uma sessão vive só na memória do processo que a abriu. Em código
> de verdade, mantenha um `vault` pela vida inteira do processo — e leia [Sessões](sessions.pt-BR.md) antes de rodá-lo
> num servidor.

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
diagnos whoami                                  # prova o token; imprime os grupos dele
diagnos patients create --group sg_oncology --legal-name "Maria da Silva" --display-name Maria
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology scans/IM-0001.dcm
```

Cada invocação do `diagnos` abre a própria sessão com o token guardado, sem prompt — o [guia da CLI](cli.pt-BR.md)
explica como rodá-la em scripts e cron.

## Para onde ir agora

| Para… | Leia |
|---|---|
| entender workspaces, grupos, versões e nós | [Conceitos](concepts.pt-BR.md) |
| ler, atualizar, arquivar e apagar com segurança | [Pacientes](patients.pt-BR.md) · [Exames](exams.pt-BR.md) · [Arquivos](files.pt-BR.md) |
| rodar num servidor, com o token no OpenBao | [Sessões](sessions.pt-BR.md) · [Implantando a API](../../apps/api/deploy/README.pt-BR.md) |
| tratar toda falha | [Erros](errors.pt-BR.md) |
| chamar por HTTP em vez disso | [Guia da API REST](api.pt-BR.md) |
| saber exatamente o que o cofre consegue ver | [Modelo de segurança](security.pt-BR.md) |
