# Exames

[English](exams.md) · **Português (Brasil)**

`vault.exams` funciona como [`vault.patients`](patients.pt-BR.md) — documentos versionados e selados — com duas
diferenças que importam: todo exame pertence a um paciente, e o conteúdo dele é um laudo clínico que o editor web
abre.

## Criar

```python
from diagnos import Diagnos, ExamRecord

vault = Diagnos()
patient = vault.patients.create(
    {"legal_name": "Maria da Silva", "display_name": "Maria"}, security_group="sg_radiology"
)

exam = vault.exams.create(
    ExamRecord(title="TC de tórax", modality="CT", exam_date="2026-09-01", report_html="<p>Sem alterações.</p>"),
    patient_id=patient.id,  # obrigatório, e o único campo enviado em claro
    security_group="sg_radiology",
)
print(exam.id, exam.patient_id, exam.version_id)
```

`patient_id` é obrigatório e viaja em claro de propósito: é como o cofre liga um exame ao paciente — para rotear e
autorizar — sem abrir nenhum dos dois. Todo o resto, a modalidade inclusive, é selado. Como qualquer documento, um
exame pertence a exatamente um security group.

### O registro

| Campo | Observações |
|---|---|
| `title` | ex.: `TC de tórax` |
| `modality` | ex.: `CT`, `MR`, `US` — selado, não metadado |
| `exam_date` | uma `date`, um `datetime` com fuso ou uma string ISO; gravado e truncado como as [datas de um paciente](patients.pt-BR.md#datas-e-precisão-de-tempo) |
| `report_lexical` | o estado do editor web, como string JSON — a fonte da verdade do laudo |
| `report_html` | HTML derivado dele, para leitores que nunca abrem o editor |
| `custom_attributes` | qualquer objeto JSON |

Um `dict` funciona tão bem quanto um `ExamRecord`, com a mesma [proteção contra erro de
digitação](patients.pt-BR.md#erros-de-digitação-são-recusados-campos-desconhecidos-são-mantidos). `patient_id` ou
`report` dentro do registro são recusados, com a indicação de onde pertencem.

### O laudo

O editor web guarda um laudo como estado do Lexical (`report_lexical`) e deriva `report_html` dele. Quando você
produz um laudo que pessoas vão abrir no app web, grave **os dois**: só com `report_html`, o editor abre um documento
vazio. Um leitor que só exibe laudos pode contar apenas com `report_html` — a CLI faz exatamente isso, imprimindo-o
como texto puro.

Se um laudo é rascunho ou publicado (`exam.report_status`: `draft`, `published`, ou `None` quando nunca definido) é
metadado em claro no índice do exame. O SDK o lê e nunca o define.

## Ler

```python
exam = vault.exams.get(exam.id)  # o conteúdo mais novo; um rascunho do editor web mais novo vence
print(exam.record.title, exam.patient_id, exam.report_status, exam.from_draft)
print(exam.record.report_html)

committed = vault.exams.get(exam.id, include_draft=False)
```

Rascunhos, versões e o `index` se comportam exatamente como nos [pacientes](patients.pt-BR.md#ler).

## Listar

```python
for row in vault.exams.iter_all(security_group="sg_radiology"):
    summary = row.summary  # título, modalidade e data, decifrados localmente
    print(row.id, row.index.meta.get("patient_id"), summary.title if summary else "—")

of_patient = [row for row in vault.exams.iter_all() if row.index.meta.get("patient_id") == patient.id]
print(len(of_patient), "exame(s) de", patient.id)
```

As listas filtram por `security_group` e `include_deleted`. Não existe filtro por paciente no servidor; o id do
paciente está no `meta` em claro de cada linha, então filtrar localmente só custa o percurso.

## Atualizar

```python
current = vault.exams.get(exam.id)
signed_off = current.record.model_copy(update={"report_html": "<p>Sem alterações. Sem nódulos.</p>"})
exam = vault.exams.update(exam.id, signed_off, expected_latest_version_id=current.index.latest_version_id)
```

Como nos pacientes: uma versão nova e completa toda vez, e `expected_latest_version_id` transforma um salvamento
concorrente num `ConflictError` em vez de uma sobrescrita silenciosa — veja [Gravações concorrentes
seguras](patients.pt-BR.md#gravações-concorrentes-seguras). Exames não têm tags.

## Arquivar, apagar, restaurar

```python
vault.exams.archive(exam.id)  # uma flag, sem versão nova
vault.exams.unarchive(exam.id)
vault.exams.delete(exam.id)  # para a lixeira, nunca apagar de verdade
vault.exams.restore(exam.id)
```

## Arquivos de um exame

Imagens, séries DICOM e PDFs não fazem parte do registro: são [arquivos](files.pt-BR.md) ligados ao exame por
`exam_id`, cada um sob a própria chave.

```python
drive = vault.drives.drive("sg_radiology")
drive.upload("scans/IM-0001.dcm", exam_id=exam.id)
print([drive.name_of(node) for node in drive.iter_all(exam_id=exam.id)])
```
