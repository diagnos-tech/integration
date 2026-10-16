"""🇺🇸 `DiagnosToken`: the codec's verdicts as typed errors, what the token exposes, and what it never lets out.

The CRC message is the one a person sees when a terminal cut the token
short, so it is asserted word for word in both languages; the seed and the
token text must never reach a `repr`, a pickle, an error message or a local
of any SDK frame in a traceback.

🇧🇷 `DiagnosToken`: os vereditos do codec como erros tipados, o que o token expõe, e o que ele nunca deixa sair.

A mensagem do CRC é a que uma pessoa vê quando o terminal cortou o token,
então é conferida palavra por palavra nos dois idiomas; a semente e o texto
do token nunca podem chegar a um `repr`, um pickle, uma mensagem de erro ou
uma local de qualquer quadro do SDK num traceback.
"""

from __future__ import annotations

import copy
import json
import pickle
import secrets
from typing import Any

import pytest
from _tokens import legacy_token, mint

from diagnos import ConfigError, TokenError
from diagnos.transport.service_token import DiagnosToken

from conftest import VECTORS

VECTOR = json.loads((VECTORS / "service-account-token-v1.json").read_text(encoding="utf-8"))
INVALID: list[dict[str, str]] = VECTOR["invalid_tokens"]


def test_a_vector_token_exposes_its_identity_and_the_reference_public_keys() -> None:
    """🇺🇸 Key id, workspace, identity and all four public keys equal the reference's.

    🇧🇷 Id da chave, workspace, identidade e as quatro chaves públicas iguais às da referência.
    """
    for vector in VECTOR["vectors"]:
        token = DiagnosToken.parse(f"  {vector['token']}\n")
        assert (token.key_id, token.workspace_id) == (vector["key_id"], vector["workspace_id"])
        assert token.identity == vector["identity"]
        assert token.public_keys == vector["public_keys"]
        assert token.source == "DIAGNOS_TOKEN"


@pytest.mark.parametrize("case", INVALID, ids=[case["name"] for case in INVALID])
def test_every_invalid_vector_is_refused_for_its_reason_before_any_network(case: dict[str, str]) -> None:
    """🇺🇸 Same `reason` as the reference; a legacy `apikey-` says where it belongs instead.

    🇧🇷 Mesmo `reason` da referência; um `apikey-` legado diz onde deveria estar.
    """
    with pytest.raises(TokenError) as caught:
        DiagnosToken.parse(case["token"], source="DIAGNOS_TOKEN")
    error = caught.value
    assert error.reason == case["reason"]
    assert isinstance(error, ConfigError)
    assert case["token"] not in str(error)
    assert str(error).startswith("DIAGNOS_TOKEN ")
    if case["token"].startswith("apikey-"):
        assert "DIAGNOS_API_TOKEN" in str(error)


def test_a_cut_token_says_truncated_or_pasted_wrong_in_both_languages() -> None:
    """🇺🇸 Every way of losing characters ends in the same plain advice. 🇧🇷 Perder caracteres dá o mesmo conselho."""
    text = mint()
    for cut in range(1, 12):
        with pytest.raises(TokenError) as caught:
            DiagnosToken.parse(text[:-cut], source="keyring")
        message = str(caught.value)
        assert caught.value.reason in {"encoding", "length", "checksum"}
        assert "the token is truncated or was pasted wrong" in message
        assert "o token está truncado ou foi colado errado" in message
        assert text[8:40] not in message


def test_empty_and_foreign_texts_name_the_fix() -> None:
    """🇺🇸 Empty, another secret, the legacy token: three different answers. 🇧🇷 Vazio, outro segredo, o legado."""
    for text, reason, advice in (
        ("   ", "empty", "is empty"),
        ("ghp_" + secrets.token_hex(20), "prefix", "dgn_sk1_"),
        (legacy_token(), "prefix", "DIAGNOS_API_TOKEN"),
    ):
        with pytest.raises(TokenError, match=advice) as caught:
            DiagnosToken.parse(text)
        assert caught.value.reason == reason
    with pytest.raises(ConfigError, match="DIAGNOS_TOKEN is not set"):
        DiagnosToken.from_env({})
    assert DiagnosToken.from_env({"DIAGNOS_TOKEN": mint("wsEnv")}).workspace_id == "wsEnv"


def test_repr_pickle_and_copy_never_carry_the_secret() -> None:
    """🇺🇸 `repr`/`str` show the identity only; pickle and copy are refused; `wipe` ends signing.

    🇧🇷 `repr`/`str` mostram só a identidade; pickle e cópia são recusados; `wipe` acaba com a assinatura.
    """
    text = mint("wsRepr")
    token = DiagnosToken.parse(text)
    for shown in (repr(token), str(token)):
        assert shown == f"DiagnosToken(identity='{token.identity}', seed='<redacted>')"
        assert text[8:] not in shown
    for attempt in (pickle.dumps, copy.copy, copy.deepcopy):
        with pytest.raises(TypeError, match="DiagnosToken"):
            attempt(token)
    assert len(token.sign(b"m")) == 64 + 3309
    token.wipe()
    assert token.is_wiped
    with pytest.raises(Exception, match="wiped"):
        token.sign(b"m")
    half_built = DiagnosToken.__new__(DiagnosToken)
    assert repr(half_built) == "DiagnosToken(identity='svc_…@….diagnos.health', seed='<redacted>')"


def test_the_seal_pair_is_a_copy_its_owner_wipes() -> None:
    """🇺🇸 `keypair()` hands out the token's X25519 + ML-KEM-768 publics; wiping it leaves the token whole.

    🇧🇷 `keypair()` entrega as públicas X25519 + ML-KEM-768 do token; apagá-lo deixa o token inteiro.
    """
    vector = VECTOR["vectors"][0]
    token = DiagnosToken.parse(vector["token"])
    pair = token.keypair()
    assert pair.public_keys_b64url() == {
        "x25519": vector["public_keys"]["x25519"],
        "mlkem768": vector["public_keys"]["ml_kem_768"],
    }
    pair.zeroize()
    assert pair.is_wiped and not token.is_wiped


def _locals_hold(error: BaseException, secret: str) -> list[str]:
    """🇺🇸 SDK-frame locals whose `repr` has `secret`. 🇧🇷 Locais de quadros do SDK cujo `repr` tem `secret`."""
    found: list[str] = []
    tb = error.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        if frame.f_code.co_filename != __file__:
            found += [
                f"{frame.f_code.co_name}.{name}" for name, value in frame.f_locals.items() if secret in repr(value)
            ]
        tb = tb.tb_next
    return found


@pytest.mark.parametrize("damage", ["cut", "swap", "legacy"])
def test_no_traceback_frame_keeps_the_text_of_a_rejected_token(damage: str) -> None:
    """🇺🇸 Whatever the failure, no SDK frame in the traceback holds the token text (or its seed half).

    🇧🇷 Seja qual for a falha, nenhum quadro do SDK no traceback guarda o texto do token (nem a metade da semente).
    """
    text = mint("wsTrace")
    bad = {"cut": text[:-3], "swap": text[:30] + ("A" if text[30] != "A" else "B") + text[31:]}.get(damage)
    bad = bad if bad is not None else "apikey-" + text
    with pytest.raises(TokenError) as caught:
        DiagnosToken.parse(bad)
    # 🇺🇸 A window past the swapped character, inside every damaged form. 🇧🇷 Uma janela depois do caractere trocado.
    assert _locals_hold(caught.value, text[40:70]) == []


def test_formatted_tracebacks_never_show_the_token() -> None:
    """🇺🇸 The rendered traceback (what a log handler writes) has no byte of the text.

    🇧🇷 O traceback renderizado (o que um handler de log escreve) não tem um byte do texto.
    """
    import traceback

    text = mint("wsTrace")
    bad = text[:-2]
    try:
        DiagnosToken.parse(bad)
    except TokenError as exc:
        rendered = "".join(traceback.format_exception(exc))
    assert text[12:60] not in rendered
    assert "truncated or was pasted wrong" in rendered


def test_the_parsed_token_signs_with_every_key_it_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `public_keys` are what verify its signatures. 🇧🇷 As `public_keys` são o que verificam as assinaturas."""
    from diagnos.crypto.encoding import b64url_decode
    from diagnos.crypto.token_keys import verify_signature

    token = DiagnosToken.parse(mint())
    keys: dict[str, Any] = {name: b64url_decode(value) for name, value in token.public_keys.items()}
    assert [len(keys[name]) for name in ("ed25519", "ml_dsa_65", "x25519", "ml_kem_768")] == [32, 1952, 32, 1184]
    assert verify_signature(keys["ed25519"], keys["ml_dsa_65"], b"base", token.sign(b"base"))
