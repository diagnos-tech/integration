"""🇺🇸 The token vectors through the Python wrappers, plus independent oracles and the copy's provenance.

`vectors/service-account-token-v1.json` is a verbatim copy of the monorepo's
`packages/security-module/test-vectors/service-account-token-v1.json`
(spec §3: "the SDK copies the same file and fails if it diverges"). The
Rust core runs it in `apps/sdk/native/tests/token_vectors.rs`; here the same
file goes through `DiagnosToken` and the session's AADs, and `cryptography`
recomputes the HKDF outputs on its own. With `DIAGNOS_MONOREPO` pointing at
a monorepo checkout, the copy is also compared with its source byte for byte.

🇧🇷 Os vetores do token pelos wrappers Python, mais oráculos independentes e a procedência da cópia.

`vectors/service-account-token-v1.json` é uma cópia literal do
`packages/security-module/test-vectors/service-account-token-v1.json` do
monorepo (spec §3: "o SDK copia o mesmo arquivo e reprova se divergir"). O
núcleo Rust o roda em `apps/sdk/native/tests/token_vectors.rs`; aqui o mesmo
arquivo passa pelo `DiagnosToken` e pelos AADs da sessão, e o `cryptography`
recalcula as saídas do HKDF por conta própria. Com `DIAGNOS_MONOREPO`
apontando para um checkout do monorepo, a cópia também é comparada com a
origem byte a byte.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from diagnos.crypto.envelope import EncryptedPayload
from diagnos.session.token_session import GROUP_KEY_AAD_PREFIX, SESSION_AAD_PREFIX, group_key_aad, session_aad
from diagnos.transport.service_token import DiagnosToken

from conftest import VECTORS

FILE = VECTORS / "service-account-token-v1.json"
DATA: dict[str, Any] = json.loads(FILE.read_text(encoding="utf-8"))
SOURCE = Path("packages/security-module/test-vectors/service-account-token-v1.json")


def test_constants_are_the_sdks() -> None:
    """🇺🇸 Prefix, AAD prefixes and the frozen seal label agree with the reference. 🇧🇷 Constantes iguais à referência."""
    constants = DATA["constants"]
    assert constants["token_prefix"] == "dgn_sk1_"  # noqa: S105 — a format prefix, not a secret
    assert constants["signature_alg"] == "ed25519+ml-dsa-65"
    assert constants["session_seal_aad_prefix"] == SESSION_AAD_PREFIX
    assert constants["group_kek_seal_aad_prefix"] == GROUP_KEY_AAD_PREFIX


@pytest.mark.parametrize("vector", DATA["vectors"], ids=[vector["name"] for vector in DATA["vectors"]])
def test_hkdf_outputs_match_an_independent_implementation(vector: dict[str, Any]) -> None:
    """🇺🇸 `cryptography`'s HKDF over the vector seed gives the reference's four outputs. 🇧🇷 HKDF independente."""
    seed = bytes.fromhex(vector["seed_hex"])
    for label, expected in vector["hkdf_output_hex"].items():
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=len(expected) // 2,
            salt=DATA["constants"]["hkdf_salt"].encode(),
            info=label.encode(),
        ).derive(seed)
        assert derived.hex() == expected, label


def test_both_seals_open_with_the_tokens_pair_and_the_sdks_aads() -> None:
    """🇺🇸 The SDK's AAD strings are the reference's; the group KEK and the session plaintext come out exactly.

    🇧🇷 As strings de AAD do SDK são as da referência; a KEK do grupo e o texto da sessão saem exatamente.
    """
    owner = DATA["vectors"][0]
    token = DiagnosToken.parse(owner["token"])
    seals = DATA["seals"]
    group = seals["group_kek"]
    assert group_key_aad(token.workspace_id, token.key_id, group["security_group_id"]) == group["aad"]
    assert session_aad(token.workspace_id, token.key_id) == seals["session"]["aad"]
    pair = token.keypair()
    kek = pair.open_secret(EncryptedPayload.from_dict(group["sealed"]), group["aad"])
    assert bytes(kek.reveal()).hex() == group["kek_hex"]
    opened = pair.open_session(EncryptedPayload.from_dict(seals["session"]["sealed"]), seals["session"]["aad"])
    plaintext = json.loads(seals["session"]["plaintext_utf8"])
    assert (opened.session_id, opened.expires_at) == (plaintext["session_id"], plaintext["expires_at"])


@pytest.mark.skipif(not os.environ.get("DIAGNOS_MONOREPO"), reason="DIAGNOS_MONOREPO not set · não definida")
def test_the_copy_is_byte_for_byte_the_monorepos_file() -> None:
    """🇺🇸 The vendored vectors equal the reference's current file. 🇧🇷 A cópia é igual ao arquivo atual."""
    source = Path(os.environ["DIAGNOS_MONOREPO"]) / SOURCE
    assert source.read_bytes() == FILE.read_bytes()
