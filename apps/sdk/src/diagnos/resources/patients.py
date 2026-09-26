"""🇺🇸 `Patients`: the patient-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`).

🇧🇷 `Patients`: a face de paciente de `VersionedDocuments` (`docs/PROTOCOL.md §8`).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from diagnos.dates import TimePrecision, truncate_timestamp
from diagnos.models import DocumentIndex, Page, Patient, PatientListItem, PatientRecord, PatientSummary

from ._documents import DEFAULT_PAGE_SIZE, OpenedDocument, VersionedDocuments, coerce_record


def require_single_group(security_group: object) -> str:
    """🇺🇸 A document belongs to exactly one security group; a list is a mistake worth explaining.

    🇧🇷 Um documento pertence a exatamente um security group; uma lista é um engano que vale explicar.
    """
    if isinstance(security_group, str) and security_group:
        return security_group
    raise TypeError(
        "security_group must be one security group id (a str): a document belongs to exactly one group, and "
        "sharing it with another team means copying it · security_group precisa ser um id de security group (str): "
        "um documento pertence a exatamente um grupo, e compartilhá-lo com outra equipe é copiá-lo"
    )


class Patients:
    """🇺🇸 `vault.patients` — list, read, create, update, archive/unarchive, delete/restore.

    🇧🇷 `vault.patients` — listar, ler, criar, atualizar, arquivar/desarquivar, apagar/restaurar.
    """

    def __init__(
        self,
        documents: VersionedDocuments[PatientRecord, PatientSummary],
        *,
        time_precision: TimePrecision | None = None,
    ) -> None:
        """🇺🇸 Wraps a `VersionedDocuments` for `patients`; `time_precision` truncates dates before sealing.

        🇧🇷 Envolve um `VersionedDocuments` de `patients`; `time_precision` trunca datas antes de selar.
        """
        self._documents = documents
        self._time_precision = time_precision

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[PatientListItem]:
        """🇺🇸 One page of patients, each with its decrypted summary (names, tags) — no version downloaded.

        🇧🇷 Uma página de pacientes, cada um com o resumo decifrado (nomes, tags) — nenhuma versão baixada.
        """
        return self._documents.list(
            security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
        )

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[PatientListItem]:
        """🇺🇸 Every patient, across all pages. 🇧🇷 Todo paciente, por todas as páginas."""
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, patient_id: str, *, version_id: str | None = None, include_draft: bool = True) -> Patient:
        """🇺🇸 Fetches and decrypts one patient: the newest content, or the version `version_id` names.

        The newest content is the web app's: its draft head when that is
        newer than the latest version (`Patient.from_draft`), else the
        latest version. Pass `include_draft=False` to read only committed
        versions.

        🇧🇷 Busca e decifra um paciente: o conteúdo mais novo, ou a versão que `version_id` nomeia.

        O conteúdo mais novo é o do app web: a cabeça de rascunho quando é
        mais nova que a versão corrente (`Patient.from_draft`), senão a
        versão corrente. Passe `include_draft=False` para ler só versões
        confirmadas.
        """
        return _patient(self._documents.read(patient_id, version_id=version_id, include_draft=include_draft))

    def index(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 The patient's metadata — group, versions, flags, sealed summary — without opening the record.

        One signed read and no decryption: for "which group is this patient
        in?" or "is it archived?", not for reading the record.

        🇧🇷 O metadado do paciente — grupo, versões, flags, resumo selado — sem abrir o registro.

        Uma leitura assinada e nenhuma decifragem: para "em que grupo está
        este paciente?" ou "está arquivado?", não para ler o registro.
        """
        return self._documents.get_index(patient_id)

    def create(
        self,
        record: PatientRecord | Mapping[str, Any],
        *,
        security_group: str,
        tags: Sequence[str] = (),
        specialist_ids: Sequence[str] | None = None,
    ) -> Patient:
        """🇺🇸 Seals `record` under `security_group` and creates the patient with its first version.

        `tags` are list/search labels ("diabetes"); they are sealed inside
        the summary, never sent in clear. `specialist_ids` go to clear
        `meta` — the only patient metadata the vault itself reads.

        🇧🇷 Sela `record` sob `security_group` e cria o paciente com a primeira versão.

        `tags` são rótulos de lista/busca ("diabetes"); ficam selados dentro
        do resumo, nunca vão em claro. `specialist_ids` vão no `meta` em
        claro — o único metadado de paciente que o próprio cofre lê.
        """
        group = require_single_group(security_group)
        patient_record = self._anonymize(coerce_record(PatientRecord, record))
        meta = {"specialist_ids": list(specialist_ids)} if specialist_ids else None
        opened = self._documents.create(
            patient_record, security_group=group, summary=PatientSummary.of(patient_record, tags), meta=meta
        )
        return _patient(opened)

    def update(
        self,
        patient_id: str,
        record: PatientRecord | Mapping[str, Any],
        *,
        tags: Sequence[str] | None = None,
        specialist_ids: Sequence[str] | None = None,
        expected_latest_version_id: str | None = None,
    ) -> Patient:
        """🇺🇸 Seals a new complete version of `record`; `tags=None` keeps the current tags.

        Pass `expected_latest_version_id=patient.index.latest_version_id`
        from your earlier read to have the vault refuse the write — a
        `ConflictError` whose `code` is `"DocumentVersionMismatch"` — if
        someone else saved in between.

        🇧🇷 Sela uma versão nova e completa de `record`; `tags=None` mantém as tags atuais.

        Passe `expected_latest_version_id=patient.index.latest_version_id`
        da sua leitura anterior para o cofre recusar a gravação — um
        `ConflictError` cujo `code` é `"DocumentVersionMismatch"` — se outra
        pessoa salvou no meio-tempo.
        """
        patient_record = self._anonymize(coerce_record(PatientRecord, record))

        def summary(current: PatientSummary | None) -> PatientSummary:
            """🇺🇸 The new summary, carrying the current tags when none were given.

            🇧🇷 O resumo novo, carregando as tags atuais quando nenhuma foi dada.
            """
            kept = tags if tags is not None else (current.tags if current is not None else ())
            return PatientSummary.of(patient_record, kept)

        meta = {"specialist_ids": list(specialist_ids)} if specialist_ids is not None else None
        opened = self._documents.update(
            patient_id,
            patient_record,
            summary=summary,
            meta=meta,
            expected_latest_version_id=expected_latest_version_id,
        )
        return _patient(opened)

    def archive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Marks the patient archived (no new version). 🇧🇷 Marca o paciente arquivado (sem versão nova)."""
        return self._documents.set_flags(patient_id, is_archived=True)

    def unarchive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Clears the archived flag (no new version). 🇧🇷 Tira a flag de arquivado (sem versão nova)."""
        return self._documents.set_flags(patient_id, is_archived=False)

    def delete(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Moves the patient to the trash — a flag, never a hard delete; `restore` undoes it.

        🇧🇷 Manda o paciente para a lixeira — uma flag, nunca um apagar de verdade; `restore` desfaz.
        """
        return self._documents.set_flags(patient_id, is_deleted=True)

    def restore(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Takes the patient out of the trash. 🇧🇷 Tira o paciente da lixeira."""
        return self._documents.set_flags(patient_id, is_deleted=False)

    def _anonymize(self, record: PatientRecord) -> PatientRecord:
        """🇺🇸 Truncates `birth_date` to `time_precision`, as the web app does before sealing.

        🇧🇷 Trunca `birth_date` em `time_precision`, como o app web faz antes de selar.
        """
        if self._time_precision is None or record.birth_date is None:
            return record
        return record.model_copy(update={"birth_date": truncate_timestamp(record.birth_date, self._time_precision)})


def _patient(opened: OpenedDocument[PatientRecord, PatientSummary]) -> Patient:
    """🇺🇸 The public `Patient` for one engine result. 🇧🇷 O `Patient` público de um resultado do motor."""
    return Patient(
        index=opened.index,
        record=opened.record,
        summary=opened.summary,
        version_id=opened.version_id,
        draft_rev=opened.draft_rev,
    )
