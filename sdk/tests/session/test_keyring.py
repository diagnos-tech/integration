"""🇺🇸 `SessionKeys`/`Keyring`: expiry margin, zeroization, and the never-a-secret-in-`repr` promise.

🇧🇷 `SessionKeys`/`Keyring`: margem de expiração, zeroização, e a promessa de nunca ter segredo em `repr`.
"""

from __future__ import annotations

import pytest
from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import GroupKeyUnavailable, Keyring, SessionKeys


def _session_keys(expires_at: int = 1_000) -> SessionKeys:
    """🇺🇸 A `SessionKeys` with fixed, recognizable (non-random) key bytes, each its own `SecretBox`.

    🇧🇷 Um `SessionKeys` com bytes de chave fixos e reconhecíveis (não aleatórios), cada um seu próprio `SecretBox`.
    """
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(b"\xaa" * 32)),
        enc_key=SecretBox.from_bytes(bytearray(b"\xbb" * 32)),
        expires_at=expires_at,
    )


def test_is_valid_true_with_margin_to_spare() -> None:
    """🇺🇸 Well before `expires_at`, with margin to spare, the session is valid.

    🇧🇷 Bem antes de `expires_at`, com margem de sobra, a sessão é válida.
    """
    keys = _session_keys(expires_at=1_000)
    assert keys.is_valid(now=900, margin_seconds=60) is True  # 100 s left, margin 60 s


def test_is_valid_false_inside_the_margin() -> None:
    """🇺🇸 Inside the margin window, the session already counts as invalid.

    🇧🇷 Dentro da janela de margem, a sessão já conta como inválida.
    """
    keys = _session_keys(expires_at=1_000)
    assert keys.is_valid(now=950, margin_seconds=60) is False  # 50 s left, margin 60 s


def test_is_valid_false_once_expired() -> None:
    """🇺🇸 Past `expires_at`, the session is invalid even with zero margin.

    🇧🇷 Depois de `expires_at`, a sessão é inválida mesmo com margem zero.
    """
    keys = _session_keys(expires_at=1_000)
    assert keys.is_valid(now=1_001, margin_seconds=0) is False


def test_zeroize_overwrites_both_keys() -> None:
    """🇺🇸 `zeroize()` wipes `sign_key` and `enc_key`; either one raises `SecureError` afterwards.

    🇧🇷 `zeroize()` apaga `sign_key` e `enc_key`; qualquer uma lança `SecureError` depois.
    """
    keys = _session_keys()
    keys.zeroize()
    assert keys.sign_key.is_wiped is True
    assert keys.enc_key.is_wiped is True


def test_session_keys_repr_never_contains_key_bytes() -> None:
    """🇺🇸 `repr(keys)` shows neither key's bytes, only a redacted marker.

    🇧🇷 `repr(keys)` não mostra os bytes de nenhuma chave, só um marcador redigido.
    """
    keys = _session_keys()
    rendered = repr(keys)
    assert "\\xaa" not in rendered
    assert "\\xbb" not in rendered
    assert "redacted" in rendered


def test_keyring_group_key_returns_the_stored_box_itself() -> None:
    """🇺🇸 `group_key` hands back the exact `SecretBox` stored, not a copy — a box needs no copy to be safe.

    🇧🇷 `group_key` devolve exatamente o `SecretBox` guardado, não uma cópia — a caixa não precisa de cópia.
    """
    dek = SecretBox.from_bytes(bytearray(b"\xcc" * 32))
    keyring = Keyring(enrollment_id="enroll_1", session=_session_keys(), group_keys={"sg1": dek})

    returned = keyring.group_key("sg1")

    assert returned is dek
    assert bytes(returned.reveal()) == b"\xcc" * 32


def test_keyring_group_key_missing_raises_group_key_unavailable() -> None:
    """🇺🇸 A security group with no DEK raises `GroupKeyUnavailable`, not `KeyError`.

    🇧🇷 Um security group sem DEK lança `GroupKeyUnavailable`, não `KeyError`.
    """
    keyring = Keyring(enrollment_id="enroll_1", session=_session_keys(), group_keys={})
    with pytest.raises(GroupKeyUnavailable):
        keyring.group_key("sg-missing")


def test_keyring_security_group_ids_lists_every_group() -> None:
    """🇺🇸 `security_group_ids` lists exactly the groups this keyring holds a DEK for.

    🇧🇷 `security_group_ids` lista exatamente os grupos cuja DEK este keyring tem.
    """
    keyring = Keyring(
        enrollment_id="enroll_1",
        session=_session_keys(),
        group_keys={"sg1": SecretBox.random(32), "sg2": SecretBox.random(32)},
    )
    assert sorted(keyring.security_group_ids) == ["sg1", "sg2"]


def test_keyring_zeroize_wipes_session_and_all_group_keys() -> None:
    """🇺🇸 `zeroize()` wipes the session keys and every group DEK, not just one.

    🇧🇷 `zeroize()` apaga as chaves de sessão e toda DEK de grupo, não só uma.
    """
    keyring = Keyring(
        enrollment_id="enroll_1",
        session=_session_keys(),
        group_keys={
            "sg1": SecretBox.from_bytes(bytearray(b"\xdd" * 32)),
            "sg2": SecretBox.from_bytes(bytearray(b"\xee" * 32)),
        },
    )
    keyring.zeroize()
    assert keyring.session.sign_key.is_wiped is True
    assert keyring.session.enc_key.is_wiped is True
    assert keyring.group_keys["sg1"].is_wiped is True
    assert keyring.group_keys["sg2"].is_wiped is True


def test_keyring_repr_never_contains_group_key_bytes() -> None:
    """🇺🇸 `repr(keyring)` shows group ids (not secret) but never DEK bytes.

    🇧🇷 `repr(keyring)` mostra ids de grupo (não secretos) mas nunca bytes de DEK.
    """
    keyring = Keyring(
        enrollment_id="enroll_1",
        session=_session_keys(),
        group_keys={"sg1": SecretBox.from_bytes(bytearray(b"\xcc" * 32))},
    )
    rendered = repr(keyring)
    assert "\\xcc" not in rendered
    assert "sg1" in rendered  # 🇺🇸 group ids are not secret · 🇧🇷 id de grupo não é segredo
