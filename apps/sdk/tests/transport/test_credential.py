"""🇺🇸 `ServiceAccountCredential`: parsing the one-line form and the JSON file, discovery order, and secrecy.

Every credential here is generated at test time (`secrets`), so no key —
real or fake — is ever committed. The Ed25519 results are cross-checked
against PyNaCl, an implementation independent of the Rust enclave.

🇧🇷 `ServiceAccountCredential`: leitura da forma de uma linha e do arquivo JSON, ordem de descoberta, e sigilo.

Toda credencial aqui é gerada na hora do teste (`secrets`), então nenhuma
chave — real ou falsa — é commitada. Os resultados Ed25519 são conferidos
contra o PyNaCl, uma implementação independente do enclave em Rust.
"""

from __future__ import annotations

import json
import pickle
import secrets
from pathlib import Path
from typing import Any

import pytest
from nacl.signing import SigningKey, VerifyKey

from diagnos.crypto.encoding import b64url_decode, b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import ConfigError, CryptoError
from diagnos.transport.credential import ServiceAccountCredential
from diagnos.transport.credential_file import find_identity
from diagnos.transport.credential_text import mask_identity


def fresh(workspace: str = "wsTest") -> tuple[str, str, bytes]:
    """🇺🇸 A generated `(line, identity, seed)`. 🇧🇷 Uma `(linha, identidade, semente)` gerada na hora."""
    seed = secrets.token_bytes(32)
    identity = f"svc_{secrets.token_hex(16)}@{workspace}.diagnos.health"
    return f"{identity}:{b64url_encode(seed)}", identity, seed


def write_file(path: Path, identity: str, seed: bytes, overrides: dict[str, Any] | None = None) -> Path:
    """🇺🇸 A credential file shaped like the one the panel downloads. 🇧🇷 Um arquivo como o que o painel baixa."""
    key_id, _, rest = identity.partition("@")
    data = {
        "type": "diagnos_service_account",
        "version": 1,
        "identity": identity,
        "key_id": key_id,
        "workspace_id": rest.removesuffix(".diagnos.health"),
        "private_key": b64url_encode(seed),
        "service_account": "ingest-bot",
        "created_at": "2026-10-15T12:00:00Z",
        **(overrides or {}),
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_parse_reads_identity_and_derives_the_public_key_pynacl_agrees_with() -> None:
    """🇺🇸 Identity fields, and a public key/signature PyNaCl reproduces. 🇧🇷 Campos e chave que o PyNaCl reproduz."""
    line, identity, seed = fresh()
    credential = ServiceAccountCredential.parse(line)
    assert credential.identity == identity
    assert credential.key_id == identity.split("@")[0]
    assert credential.workspace_id == "wsTest"
    assert credential.signs_requests is True
    oracle = SigningKey(seed)
    assert b64url_decode(credential.public_key) == bytes(oracle.verify_key)
    assert credential.sign(b"hello") == oracle.sign(b"hello").signature
    VerifyKey(bytes(oracle.verify_key)).verify(b"hello", credential.sign(b"hello"))


def test_parse_splits_on_the_last_colon_and_trims_whitespace() -> None:
    """🇺🇸 A trailing newline from `cat` or a paste is harmless. 🇧🇷 Uma quebra de linha final não atrapalha."""
    line, identity, _ = fresh()
    assert ServiceAccountCredential.parse(f"  {line}\n").identity == identity


@pytest.mark.parametrize(
    ("mangle", "fragment"),
    [
        (lambda line: line.replace(":", ""), "no ':'"),
        (lambda line: line.replace("svc_", "acct_"), "identity is malformed"),
        (lambda line: line.replace(".diagnos.health", ".example.com"), "identity is malformed"),
        (lambda line: line[:-1], "canonical 43-character"),
        (lambda line: line + "A", "canonical 43-character"),
        (lambda line: line[:-2] + "+/", "canonical 43-character"),
    ],
)
def test_malformed_lines_are_config_errors_that_never_echo_the_key(mangle: Any, fragment: str) -> None:
    """🇺🇸 Each mistake names itself and the expected shape — and never repeats the key.

    🇧🇷 Cada erro diz o que é e a forma esperada — e nunca repete a chave.
    """
    line, _, seed = fresh()
    with pytest.raises(ConfigError) as caught:
        ServiceAccountCredential.parse(mangle(line))
    message = str(caught.value)
    assert fragment in message
    assert "svc_<32 hex>@<workspace_id>.diagnos.health" in message
    assert b64url_encode(seed)[:12] not in message


def test_a_legacy_token_in_the_new_variable_points_to_the_right_one() -> None:
    """🇺🇸 `apikey-…` pasted into `DIAGNOS_CREDENTIAL` says where it belongs. 🇧🇷 Diz onde o token legado deve ir."""
    with pytest.raises(ConfigError, match="DIAGNOS_API_TOKEN"):
        ServiceAccountCredential.parse("apikey-aaa.bbb.ccc")


def test_repr_str_and_format_mask_everything_secret() -> None:
    """🇺🇸 Neither the seed nor the full key id shows up in `repr`, `str` or an f-string.

    🇧🇷 Nem a semente nem o key id completo aparecem em `repr`, `str` ou numa f-string.
    """
    line, identity, seed = fresh()
    credential = ServiceAccountCredential.parse(line)
    key_hex = identity[4:36]
    for text in (repr(credential), str(credential), f"{credential}", f"{credential!r}"):
        assert b64url_encode(seed) not in text
        assert key_hex not in text
        assert "<redacted>" in text
    assert mask_identity(identity) in repr(credential)
    assert mask_identity("not an identity") == "svc_…"


def test_a_credential_cannot_be_pickled() -> None:
    """🇺🇸 Pickling would write the seed to disk. 🇧🇷 Serializar gravaria a semente em disco."""
    credential = ServiceAccountCredential.parse(fresh()[0])
    with pytest.raises(TypeError):
        pickle.dumps(credential)


def test_wipe_leaves_a_credential_that_can_no_longer_sign() -> None:
    """🇺🇸 After `wipe()`, signing fails instead of using zeros. 🇧🇷 Depois de `wipe()`, assinar falha."""
    credential = ServiceAccountCredential.parse(fresh()[0])
    credential.wipe()
    with pytest.raises(CryptoError):
        credential.sign(b"m")


def test_from_file_loads_the_downloaded_json(tmp_path: Path) -> None:
    """🇺🇸 The panel's file round-trips, name included. 🇧🇷 O arquivo do painel funciona, nome incluso."""
    _, identity, seed = fresh()
    credential = ServiceAccountCredential.from_file(write_file(tmp_path / "c.json", identity, seed))
    assert credential.identity == identity
    assert credential.service_account == "ingest-bot"
    assert credential.source == str(tmp_path / "c.json")
    assert credential.sign(b"m") == SigningKey(seed).sign(b"m").signature


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"type": "something_else"}, "not a diagnos credential file"),
        ({"version": 2}, "upgrade"),
        ({"identity": 7}, "'identity'"),
        ({"private_key": ""}, "'private_key'"),
        ({"key_id": "svc_" + "0" * 32}, "'key_id' disagrees"),
        ({"workspace_id": "other"}, "'workspace_id' disagrees"),
    ],
)
def test_bad_credential_files_are_config_errors(tmp_path: Path, overrides: dict[str, Any], fragment: str) -> None:
    """🇺🇸 Wrong type, newer version, missing or edited fields. 🇧🇷 Tipo errado, versão nova, campo faltando/editado."""
    _, identity, seed = fresh()
    path = write_file(tmp_path / "c.json", identity, seed, overrides)
    with pytest.raises(ConfigError, match=fragment):
        ServiceAccountCredential.from_file(path)


def test_unreadable_and_non_json_files_are_config_errors(tmp_path: Path) -> None:
    """🇺🇸 A missing path or a non-JSON file says so. 🇧🇷 Caminho ausente ou arquivo não JSON dizem isso."""
    with pytest.raises(ConfigError, match="could not be read"):
        ServiceAccountCredential.from_file(tmp_path / "missing.json")
    (tmp_path / "x.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not a diagnos credential file"):
        ServiceAccountCredential.from_file(tmp_path / "x.json")


def test_a_world_readable_file_still_loads_but_warns(tmp_path: Path) -> None:
    """🇺🇸 Like `ssh`: loads, and says `chmod 600`. 🇧🇷 Como o `ssh`: carrega, e diz `chmod 600`."""
    _, identity, seed = fresh()
    path = write_file(tmp_path / "c.json", identity, seed)
    path.chmod(0o644)
    with pytest.warns(UserWarning, match="chmod 600"):
        ServiceAccountCredential.from_file(path)


def test_discovery_order_is_variable_then_file_then_legacy_token_then_default(tmp_path: Path) -> None:
    """🇺🇸 `DIAGNOS_CREDENTIAL` > `DIAGNOS_CREDENTIALS_FILE` > `DIAGNOS_API_TOKEN` > the default file.

    🇧🇷 `DIAGNOS_CREDENTIAL` > `DIAGNOS_CREDENTIALS_FILE` > `DIAGNOS_API_TOKEN` > `~/.config/diagnos/credentials.json`.
    """
    line, from_variable, _ = fresh("wsVar")
    _, from_file, file_seed = fresh("wsFile")
    _, from_default, default_seed = fresh("wsHome")
    named = write_file(tmp_path / "named.json", from_file, file_seed)
    (tmp_path / ".config" / "diagnos").mkdir(parents=True)
    write_file(tmp_path / ".config" / "diagnos" / "credentials.json", from_default, default_seed)
    env = {"HOME": str(tmp_path), "DIAGNOS_API_TOKEN": "apikey-legacy"}

    full = {**env, "DIAGNOS_CREDENTIAL": line, "DIAGNOS_CREDENTIALS_FILE": str(named)}
    assert find_identity(full).credential is not None
    assert find_identity(full).credential.identity == from_variable  # type: ignore[union-attr]
    by_file = find_identity({**env, "DIAGNOS_CREDENTIALS_FILE": str(named)}).credential
    assert by_file is not None
    assert by_file.identity == from_file
    assert find_identity(env).api_token == env["DIAGNOS_API_TOKEN"]
    by_default = find_identity({"HOME": str(tmp_path)}).credential
    assert by_default is not None
    assert by_default.identity == from_default
    assert find_identity({"HOME": str(tmp_path / "empty")}).credential is None


def test_from_env_without_any_credential_explains_every_option(tmp_path: Path) -> None:
    """🇺🇸 The error lists the variable, the file variable and the default path. 🇧🇷 O erro lista as três opções."""
    with pytest.raises(ConfigError) as caught:
        ServiceAccountCredential.from_env({"HOME": str(tmp_path)})
    for option in ("DIAGNOS_CREDENTIAL", "DIAGNOS_CREDENTIALS_FILE", "~/.config/diagnos/credentials.json"):
        assert option in str(caught.value)
    line, identity, _ = fresh()
    assert ServiceAccountCredential.from_env({"DIAGNOS_CREDENTIAL": line}).identity == identity


def test_the_constructor_refuses_a_seed_that_is_not_32_bytes() -> None:
    """🇺🇸 A 31-byte box is refused before any signing. 🇧🇷 Uma caixa de 31 bytes é recusada antes de assinar."""
    _, identity, _ = fresh()
    with pytest.raises(ConfigError, match="not 32 bytes"):
        ServiceAccountCredential(identity, SecretBox.from_bytes(bytearray(secrets.token_bytes(31))))


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


def test_no_traceback_frame_keeps_the_key_of_a_rejected_line() -> None:
    """🇺🇸 Bad identity, swapped halves, legacy prefix: no SDK frame local holds the key when the error is raised.

    🇧🇷 Identidade ruim, metades trocadas, prefixo legado: nenhuma local de quadro do SDK guarda a chave no erro.
    """
    _, identity, seed = fresh()
    key = b64url_encode(seed)
    bad_identity = identity.replace("svc_", "acct_")
    for line in (f"{bad_identity}:{key}", f"{key}:{identity}", f"apikey-{key}", f"{identity}:{key}x"):
        with pytest.raises(ConfigError) as caught:
            ServiceAccountCredential.parse(line)
        assert _locals_hold(caught.value, key) == [], line


@pytest.mark.parametrize(
    "overrides",
    [{"identity": "svc_bad@ws.diagnos.health"}, {"key_id": "svc_" + "0" * 32}, {"version": 9}, {"type": "x"}],
)
def test_no_traceback_frame_keeps_the_key_of_a_rejected_file(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """🇺🇸 Same for the JSON file: the text and the parsed `private_key` are gone before any `raise`.

    🇧🇷 O mesmo para o arquivo JSON: o texto e o `private_key` lido somem antes de qualquer `raise`.
    """
    _, identity, seed = fresh()
    path = write_file(tmp_path / "c.json", identity, seed, overrides)
    with pytest.raises(ConfigError) as caught:
        ServiceAccountCredential.from_file(path)
    assert _locals_hold(caught.value, b64url_encode(seed)) == []


def test_only_the_canonical_last_character_is_accepted() -> None:
    """🇺🇸 Like the vault: 4 useful bits in the last char, so a non-canonical spelling is refused.

    🇧🇷 Como o cofre: 4 bits úteis no último caractere, então uma grafia não canônica é recusada.
    """
    line, _, _ = fresh()
    for last in "BZz9_-":
        with pytest.raises(ConfigError, match="canonical"):
            ServiceAccountCredential.parse(line[:-1] + last)


def test_a_credential_in_the_legacy_variable_says_to_use_diagnos_credential() -> None:
    """🇺🇸 `svc_…:…` in `DIAGNOS_API_TOKEN` (or `--token`) names the right variable. 🇧🇷 Diz a variável certa."""
    with pytest.raises(ConfigError, match="This is a credential: use DIAGNOS_CREDENTIAL"):
        find_identity({"DIAGNOS_API_TOKEN": fresh()[0]})
