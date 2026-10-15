"""🇺🇸 `Diagnos` with the service account credential: every way to pass it, the identity it exposes, the legacy path.

🇧🇷 `Diagnos` com a credencial de conta de serviço: toda forma de passá-la, a identidade exposta, o caminho legado.
"""

from __future__ import annotations

import json
import secrets
import warnings
from pathlib import Path
from typing import Any

import pytest

from diagnos import Diagnos, LegacyTokenWarning, ServiceAccountCredential, Settings
from diagnos.crypto.encoding import b64url_encode
from diagnos.errors import ConfigError


def fresh() -> tuple[str, str, str]:
    """🇺🇸 A generated `(line, identity, encoded seed)`. 🇧🇷 Uma `(linha, identidade, semente)` gerada agora."""
    identity = f"svc_{secrets.token_hex(16)}@wsClient.diagnos.health"
    seed = b64url_encode(secrets.token_bytes(32))
    return f"{identity}:{seed}", identity, seed


def legacy_token() -> str:
    """🇺🇸 A syntactically valid, unsigned `apikey-<jwt>`. 🇧🇷 Um `apikey-<jwt>` sintaticamente válido, sem assinatura."""
    claims = {"sub": "key_9", "account_id": "acc_9", "workspace_id": "wsLegacy", "name": "bot@wsLegacy.diagnos.health"}
    return f"apikey-{b64url_encode(b'{}')}.{b64url_encode(json.dumps(claims).encode())}.{b64url_encode(b'sig')}"


class _Inert:
    """🇺🇸 Stands in for the transport and the session: these tests never reach the network.

    🇧🇷 Substitui o transporte e a sessão: estes testes nunca chegam à rede.
    """

    def close(self) -> None:
        """🇺🇸 Nothing to close. 🇧🇷 Nada a fechar."""


def client(**kwargs: Any) -> Diagnos:
    """🇺🇸 `Diagnos(**kwargs)` without network. 🇧🇷 `Diagnos(**kwargs)` sem rede."""
    return Diagnos(transport=_Inert(), session=_Inert(), **kwargs)  # type: ignore[arg-type]


def test_the_one_line_form_exposes_the_identity_and_masks_it_in_repr() -> None:
    """🇺🇸 `credential="svc_…:…"`: identity properties, `account_id` is `None`, `repr` masked.

    🇧🇷 `credential="svc_…:…"`: propriedades de identidade, `account_id` é `None`, `repr` mascarado.
    """
    line, identity, seed = fresh()
    vault = client(credential=line)
    assert (vault.identity, vault.workspace_id, vault.key_id) == (identity, "wsClient", identity.split("@")[0])
    assert vault.account_id is None
    assert (vault.name, vault.email) == (None, None)
    assert vault.credential_kind == "ed25519"
    assert seed not in repr(vault)
    assert identity[4:36] not in repr(vault)
    assert repr(vault).startswith("Diagnos(workspace_id='wsClient', credential='svc_")


def test_a_path_a_credential_object_and_explicit_settings_all_work(tmp_path: Path) -> None:
    """🇺🇸 A JSON path (with the account name), an object, and an object over explicit `Settings`.

    🇧🇷 Um caminho de JSON (com o nome da conta), um objeto, e um objeto por cima de `Settings` explícitos.
    """
    line, identity, seed = fresh()
    path = tmp_path / "credentials.json"
    document = {"type": "diagnos_service_account", "version": 1, "identity": identity, "private_key": seed}
    path.write_text(json.dumps({**document, "service_account": "ingest"}), encoding="utf-8")
    path.chmod(0o600)
    from_file = client(credential=path)
    assert (from_file.name, from_file.email) == ("ingest", "ingest@wsClient.diagnos.health")
    credential = ServiceAccountCredential.parse(line)
    assert client(credential=credential).identity == identity
    settings = Settings(vault_url="https://vault.test", api_token=legacy_token())
    vault = client(settings=settings, credential=credential)
    assert (vault.identity, vault._settings.vault_url) == (identity, "https://vault.test")


def test_from_env_reads_the_mapping_it_is_given(tmp_path: Path) -> None:
    """🇺🇸 `Diagnos.from_env(env)` never needs `os.environ`. 🇧🇷 `Diagnos.from_env(env)` não precisa de `os.environ`."""
    line, identity, _ = fresh()
    vault = Diagnos.from_env({"DIAGNOS_CREDENTIAL": line, "HOME": str(tmp_path)}, transport=_Inert(), session=_Inert())
    assert vault.identity == identity
    with pytest.raises(ConfigError, match="No diagnos credential found"):
        Diagnos.from_env({"HOME": str(tmp_path)})
    with pytest.raises(ConfigError, match="No diagnos credential found"):
        client(settings=Settings())


def test_the_legacy_token_still_works_and_warns_at_the_callers_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `token=` beats a credential in the environment, keeps working, and warns *here*, not inside the SDK.

    🇧🇷 `token=` vence uma credencial no ambiente, continua funcionando, e avisa *aqui*, não dentro do SDK.
    """
    monkeypatch.setenv("DIAGNOS_CREDENTIAL", fresh()[0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        vault = client(token=legacy_token())
    legacy = [warning for warning in caught if issubclass(warning.category, LegacyTokenWarning)]
    assert len(legacy) == 1
    assert legacy[0].filename == __file__
    assert "2027-04-15" in str(legacy[0].message)
    assert "DIAGNOS_CREDENTIAL" in str(legacy[0].message)
    assert (vault.credential_kind, vault.identity, vault.account_id) == ("legacy_apikey", None, "acc_9")
    assert (vault.workspace_id, vault.key_id, vault.name) == ("wsLegacy", "key_9", "bot")
    assert vault.email == "bot@wsLegacy.diagnos.health"
    assert "api_token='apikey-…" in repr(vault)
    assert issubclass(LegacyTokenWarning, DeprecationWarning)


def test_openbao_keeps_a_credentials_session_under_its_key_id(tmp_path: Path) -> None:
    """🇺🇸 No `account_id` in a credential, so the OpenBao path is `<prefix>/<workspace>/<key_id>`.

    🇧🇷 Sem `account_id` numa credencial, o path no OpenBao é `<prefix>/<workspace>/<key_id>`.
    """
    line, identity, _ = fresh()
    settings = Settings.from_env(
        {"DIAGNOS_CREDENTIAL": line, "OPENBAO_ADDR": "https://bao.test", "HOME": str(tmp_path)}
    )
    vault = Diagnos(settings, transport=_Inert())  # type: ignore[arg-type]
    store = vault._session._store  # type: ignore[attr-defined]
    assert store._path == f"diagnos/wsClient/{identity.split('@')[0]}"
