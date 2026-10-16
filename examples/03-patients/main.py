"""🇺🇸 Create a patient, list patients and read one back.

Everything in a patient record — names, birth date, notes — is sealed in
this process before it is sent. The vault keeps ciphertext and, in clear,
only the patient's security group. Lists read a small sealed *summary*
(names, tags), so no version is downloaded to draw a table; `get` downloads
and decrypts the newest version.

🇧🇷 Cria um paciente, lista pacientes e lê um de volta.

Tudo num registro de paciente — nomes, nascimento, notas — é selado neste
processo antes de ser enviado. O cofre guarda ciphertext e, em claro, só o
security group do paciente. As listas leem um *resumo* selado e pequeno
(nomes, tags), então nenhuma versão é baixada para montar uma tabela; o
`get` baixa e decifra a versão mais nova.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date

from diagnos import ConfigError, Diagnos, DiagnosError, PatientRecord, to_iso_instant


def main() -> int:
    """🇺🇸 Creates, lists and reads; returns the exit code. 🇧🇷 Cria, lista e lê; devolve o código de saída."""
    try:
        with Diagnos() as vault:
            if not vault.security_groups:
                print("this token's scope has no security group", file=sys.stderr)
                return 3
            group = os.environ.get("DIAGNOS_GROUP") or vault.security_groups[0]

            # 🇺🇸 A typed record: a misspelled field fails here, before anything is sealed.
            # 🇧🇷 Um registro tipado: um campo com typo falha aqui, antes de qualquer selagem.
            record = PatientRecord(
                legal_name="Jane Example",
                display_name="Jane",
                birth_date=to_iso_instant(date(1990, 1, 31)),  # 🇺🇸 typed as `str` · 🇧🇷 tipado como `str`
                external_id=f"example-{uuid.uuid4().hex[:8]}",  # 🇺🇸 your own system's id · 🇧🇷 o id do seu sistema
            )
            created = vault.patients.create(record, security_group=group, tags=["example"])
            print(f"patient created: {created.id} in {created.security_group_id}")

            # 🇺🇸 `iter_all` follows the cursor across pages; each row carries its decrypted summary.
            # 🇧🇷 `iter_all` segue o cursor por todas as páginas; cada linha traz o resumo decifrado.
            rows = list(vault.patients.iter_all(security_group=group))
            print(f"patients listed: {len(rows)} in {group}")
            for row in rows[:5]:
                name = row.summary.display_name if row.summary else "(group key not available)"
                print(f"  {row.id}  {name}")

            same = vault.patients.get(created.id)
            print(f"patient read: {same.record.legal_name}, tags={same.tags}, version={same.version_id}")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except DiagnosError as error:
        print(f"{error.__class__.__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
