# Pacientes

[English](patients.md) · **Português (Brasil)**

`vault.patients` cria, lê, lista e altera registros de paciente. Tudo que é clínico é selado no seu processo antes
de sair; o que o cofre guarda é um documento versionado e cifrado que ele consegue rotear, mas nunca ler. O modelo por
trás — versões, rascunhos, o resumo selado — está em [Conceitos](concepts.pt-BR.md#documentos-pacientes-e-exames).

## Criar

```python
from datetime import date

from diagnos import Diagnos

vault = Diagnos()
patient = vault.patients.create(
    {"legal_name": "Maria da Silva", "display_name": "Maria", "birth_date": date(1990, 1, 31)},
    security_group="sg_oncology",  # exatamente um grupo por documento
    tags=["diabetes"],  # rótulos de lista e busca, selados dentro do resumo
    specialist_ids=["specialist_123"],  # metadado em claro pelo qual o cofre filtra
)
print(patient.id, patient.version_id, patient.tags)
```

O registro pode ser um `dict` ou um `PatientRecord`; de um jeito ou de outro, ele é validado antes de qualquer coisa
ser cifrada. `tags` e `specialist_ids` são argumentos, não campos do registro, porque moram em lugares diferentes: as
tags são seladas com o resumo, os ids de especialista ficam no metadado em claro para o cofre poder filtrar por eles.

### O registro

`PatientRecord` espelha os dados de paciente do app web campo a campo, então o que você grava é o que o app web lê:

| Campo | Observações |
|---|---|
| `legal_name`, `display_name` | obrigatórios |
| `external_id` | o id do paciente no seu sistema — texto puro, selado com o resto |
| `birth_date` | uma `date`, um `datetime` com fuso ou uma string ISO — veja [Datas](#datas-e-precisão-de-tempo) |
| `biological_sex` | `MALE`, `FEMALE`, `INTERSEX`, `UNDEFINED` |
| `gender_identity` | `CIS_MALE`, `CIS_FEMALE`, `TRANS_MALE`, `TRANS_FEMALE`, `NON_BINARY`, `AGENDER`, `FLUID`, `OTHER`, `PREFER_NOT_TO_SAY` |
| `race_identity` | `WHITE`, `BLACK`, `BROWN`, `YELLOW`, `INDIGENOUS`, `NOT_DECLARED` |
| `email`, `phone` | texto livre |
| `address` | `postal_code`, `street`, `number`, `complement`, `district`, `city`, `state`, `country` — todos opcionais |
| `internal_notes` | uma lista de strings |
| `custom_attributes` | qualquer objeto JSON |
| `identifiers` | documentos de identidade, selados pelo cofre — veja [Documentos de identidade](#documentos-de-identidade) |

Todo campo é selado. Tipos e padrões estão na [referência do SDK](../reference/sdk.json).

### Erros de digitação são recusados, campos desconhecidos são mantidos

O cofre nunca vê texto claro, então nada adiante perceberia um campo digitado errado — ele seria gravado sob uma
chave que ninguém lê. O registro é a última checagem, e trata duas falhas opostas:

- uma chave que **parece erro de digitação** de um campo real (`birthdate`) é recusada, nomeando o campo parecido;
  o mesmo vale para uma chave que pertence a outro lugar (`tags` dentro do registro);
- qualquer **outra chave desconhecida é mantida** como veio, para um campo que o app web acrescentou depois do
  lançamento deste SDK sobreviver a um ler-modificar-gravar em vez de ser apagado em silêncio.

```python
import pydantic

try:
    vault.patients.create(
        {"legal_name": "Maria da Silva", "display_name": "Maria", "birthdate": "1990-01-31"},
        security_group="sg_oncology",
    )
except pydantic.ValidationError as error:  # lançado antes de qualquer coisa ser cifrada ou enviada
    print(error.errors()[0]["msg"])
```

> [!NOTE]
> Um registro ruim lança `pydantic.ValidationError` (um `ValueError`) localmente. `diagnos.ValidationError` é outra
> coisa: é o cofre recusando uma requisição — veja [Erros](errors.pt-BR.md).

### Datas e precisão de tempo

`birth_date` aceita uma `date`, um `datetime` com fuso ou uma string ISO 8601, e é gravada do jeito que o app web
grava: um instante UTC, `YYYY-MM-DDTHH:MM:SS.sssZ`. Só a data significa meia-noite UTC; uma hora sem deslocamento de
UTC é recusada, porque significaria um instante diferente em cada máquina.

Um workspace também pode fixar uma **precisão de anonimização** — `month`, `day`, `hour`, `minute` ou `second` — na
qual o app web trunca toda data antes de cifrar. A API externa não expõe essa configuração, então defina
`DIAGNOS_TIME_PRECISION` com o valor do seu workspace e o SDK aplica o mesmo truncamento em toda gravação:

```python
from datetime import date

from diagnos import to_iso_instant, truncate_timestamp

print(to_iso_instant(date(1990, 1, 31)))  # 1990-01-31T00:00:00.000Z
print(truncate_timestamp("1990-01-31T15:42:10Z", "month"))  # 1990-01-01T00:00:00.000Z
```

### Documentos de identidade

`identifiers` (CPF, passaporte…) são selados pela rota de dado sensível do cofre, e abrir um é auditado — a API
externa não consegue selar um novo. O SDK carrega os valores existentes intactos num ler-modificar-gravar e recusa um
valor em texto claro. Para um id de outro sistema, use `external_id`.

## Ler

```python
same = vault.patients.get(patient.id)  # o conteúdo mais novo: um rascunho do editor web mais novo vence
print(same.record.legal_name, same.from_draft, same.version_id)

committed = vault.patients.get(patient.id, include_draft=False)  # só versões confirmadas
pinned = vault.patients.get(patient.id, version_id=patient.version_id)  # uma versão exata
```

`get()` baixa e decifra uma versão (ou o rascunho). Um `Patient` traz o `record` decifrado, o `summary` e as `tags`,
de onde veio o conteúdo (`version_id`, ou `draft_rev` quando `from_draft`) e o `index` que o cofre mantém —
`security_group_id`, `versions`, `updated_at` e as flags.

## Listar

```python
for row in vault.patients.iter_all(security_group="sg_oncology"):
    summary = row.summary  # decifrado localmente do resumo selado: nenhuma versão baixada
    print(row.id, summary.display_name if summary else "—", summary.tags if summary else [])

page = vault.patients.list(limit=20)  # uma página; siga page.next_cursor para a próxima
```

As linhas são `PatientListItem`s: o índice mais o `summary` decifrado. `summary` é `None` para um paciente cujo grupo
esta sessão não tem, em vez de derrubar a página. `include_deleted=True` acrescenta os pacientes na lixeira. A
paginação está descrita em [Conceitos](concepts.pt-BR.md#listas-e-cursores).

## Atualizar

Uma atualização grava uma versão nova **completa** — não existe atualização parcial. Leia, mude, grave:

```python
current = vault.patients.get(patient.id)
renamed = current.record.model_copy(update={"display_name": "Maria S."})
patient = vault.patients.update(
    patient.id,
    renamed,
    expected_latest_version_id=current.index.latest_version_id,  # recusa se alguém salvou no meio-tempo
)
```

`model_copy` mantém todo outro campo — inclusive os que este SDK não modela. `tags=None` (o padrão) mantém as tags
atuais; passe uma lista para substituí-las. `specialist_ids` funciona do mesmo jeito.

### Gravações concorrentes seguras

Sem `expected_latest_version_id`, a última gravação vence em silêncio. Com ele, o cofre recusa a gravação quando
outra versão foi confirmada depois da sua leitura, e você decide o que fazer:

```python
from diagnos import ConflictError

stale = patient.index.latest_version_id
vault.patients.update(patient.id, patient.record, tags=["diabetes", "retorno"])  # outra pessoa salva

try:
    vault.patients.update(patient.id, renamed, expected_latest_version_id=stale)
except ConflictError as error:
    print(error.code)  # DocumentVersionMismatch: leia de novo, combine, grave de novo
```

## Arquivar, apagar, restaurar

```python
vault.patients.archive(patient.id)  # uma flag, sem versão nova
vault.patients.unarchive(patient.id)
vault.patients.delete(patient.id)  # para a lixeira; o histórico cifrado fica
vault.patients.restore(patient.id)
```

Cada um devolve o `DocumentIndex` atualizado. Apagar nunca é apagar de verdade: o paciente some das listas até o
`restore`, ou até ser listado com `include_deleted=True`.

## O que ainda não está aqui

- O fluxo `file` do paciente — o documento rico do editor web — não é exposto; o SDK lê e grava o registro
  estruturado.
- Rascunhos são lidos, nunca gravados.

Os dois, e o resto dos limites conhecidos, estão em [COMPATIBILITY.pt-BR.md](../COMPATIBILITY.pt-BR.md#limites-conhecidos).
