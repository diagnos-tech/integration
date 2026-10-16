"""🇺🇸 Upload a file to the drive, list it, download it back and compare.

A file is a **node** of the workspace, owned by one security group. The SDK
gives it its own key, seals its name and its bytes in this process, and
uploads ciphertext straight to storage. Here: a folder, a small text file in
it, and a round trip that proves the bytes come back identical.

🇧🇷 Sobe um arquivo ao drive, lista, baixa de volta e compara.

Um arquivo é um **nó** do workspace, de um security group. O SDK dá a ele a
própria chave, sela o nome e os bytes neste processo, e sobe só ciphertext
direto para o armazenamento. Aqui: uma pasta, um arquivo de texto pequeno
dentro dela, e uma ida e volta que prova que os bytes voltam idênticos.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from diagnos import ConfigError, Diagnos, DiagnosError

PAYLOAD = b"diagnos example: this text was encrypted before it left the process.\n"


def main() -> int:
    """🇺🇸 Runs the round trip; returns the exit code. 🇧🇷 Roda a ida e volta; devolve o código de saída."""
    try:
        with Diagnos() as vault:
            if not vault.security_groups:
                print("this token's scope has no security group", file=sys.stderr)
                return 3
            group = os.environ.get("DIAGNOS_GROUP") or vault.security_groups[0]
            drive = vault.drives.drive(group)

            folder_id = drive.create_folder("diagnos-examples")
            with tempfile.TemporaryDirectory() as workdir:
                source = Path(workdir) / "hello-diagnos.txt"
                source.write_bytes(PAYLOAD)
                # 🇺🇸 `name` defaults to the file name, `mime_type` to a guess from it.
                # 🇧🇷 `name` é, por padrão, o nome do arquivo; `mime_type`, um palpite por ele.
                node = drive.upload(source, parent_id=folder_id)
            print(f"uploaded: {drive.name_of(node)} ({node.mime_type}) node={node.node_id}")

            names = [drive.name_of(child) for child in drive.iter_all(parent_id=folder_id)]
            print(f"folder has {len(names)} file(s): {', '.join(names)}")

            data = drive.download(node.node_id)  # 🇺🇸 bytes in RAM, decrypted · 🇧🇷 bytes em RAM, decifrados
            if data != PAYLOAD:
                print("downloaded bytes differ from the uploaded ones", file=sys.stderr)
                return 1
            print(f"downloaded: {len(PAYLOAD)} bytes match")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except DiagnosError as error:
        print(f"{error.__class__.__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
