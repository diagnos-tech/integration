"""🇺🇸 Where the credential comes from: two env vars, the legacy token, or the default file.

Order (service account credential spec §2, plus the legacy token):

1. `DIAGNOS_CREDENTIAL` — the one-line form;
2. `DIAGNOS_CREDENTIALS_FILE` — a path to the JSON downloaded at creation;
3. `DIAGNOS_API_TOKEN` — the deprecated `apikey-` token, still accepted
   until 2027-04-15: an explicit variable beats a file nobody named;
4. `~/.config/diagnos/credentials.json`, if it exists.

A credential file readable by group or others still loads — refusing would
break a container that mounts it with the image's defaults — but warns,
the way `ssh` warns about a private key.

🇧🇷 De onde a credencial vem: `DIAGNOS_CREDENTIAL`, `DIAGNOS_CREDENTIALS_FILE`, o token legado, o arquivo padrão.

Ordem (spec da credencial de conta de serviço §2, mais o token legado):

1. `DIAGNOS_CREDENTIAL` — a forma de uma linha;
2. `DIAGNOS_CREDENTIALS_FILE` — o caminho do JSON baixado na criação;
3. `DIAGNOS_API_TOKEN` — o token `apikey-` obsoleto, aceito até
   2027-04-15: uma variável explícita vence um arquivo que ninguém nomeou;
4. `~/.config/diagnos/credentials.json`, se existir.

Um arquivo de credencial legível pelo grupo ou por outros ainda carrega —
recusar quebraria um container que o monta com os padrões da imagem — mas
avisa, como o `ssh` avisa sobre uma chave privada.
"""

from __future__ import annotations

import json
import os
import stat
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from diagnos.errors import ConfigError

from .credential import ServiceAccountCredential, _seed_from_b64url

FILE_TYPE: Final = "diagnos_service_account"
FILE_VERSION: Final = 1
DEFAULT_CREDENTIALS_FILE: Final = Path(".config") / "diagnos" / "credentials.json"


def default_credentials_path(env: Mapping[str, str]) -> Path:
    """🇺🇸 `~/.config/diagnos/credentials.json`, `~` from `HOME` when the mapping has it.

    🇧🇷 `~/.config/diagnos/credentials.json`, com `~` vindo de `HOME` quando o mapeamento o tem.
    """
    home = env.get("HOME")
    return (Path(home) if home else Path.home()) / DEFAULT_CREDENTIALS_FILE


def _field(data: Mapping[str, Any], name: str, where: str) -> str:
    """🇺🇸 A required string field of the credential file. 🇧🇷 Um campo string obrigatório do arquivo de credencial."""
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"🇺🇸 {where}: field '{name}' is missing or not a string; download the credential file again. "
            f"🇧🇷 {where}: o campo '{name}' falta ou não é string; baixe o arquivo de credencial de novo."
        )
    return value


def credential_from_file(path: str | os.PathLike[str]) -> ServiceAccountCredential:
    """🇺🇸 Load the JSON credential file (`{"type":"diagnos_service_account","version":1,…}`).

    🇧🇷 Carrega o arquivo JSON de credencial (`{"type":"diagnos_service_account","version":1,…}`).
    """
    where = os.fspath(path)
    try:
        raw = Path(path).read_text(encoding="utf-8")
        mode = Path(path).stat().st_mode
    except OSError as exc:
        raise ConfigError(
            f"🇺🇸 {where}: the credential file could not be read ({exc.strerror}). "
            f"🇧🇷 {where}: o arquivo de credencial não pôde ser lido ({exc.strerror})."
        ) from None
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get("type") != FILE_TYPE:
        raise ConfigError(
            f'🇺🇸 {where}: not a diagnos credential file (expected JSON with "type": "{FILE_TYPE}"). '
            f'🇧🇷 {where}: não é um arquivo de credencial diagnos (esperado JSON com "type": "{FILE_TYPE}").'
        )
    if data.get("version") != FILE_VERSION:
        raise ConfigError(
            f"🇺🇸 {where}: credential file version {data.get('version')!r} is newer than this SDK knows; upgrade "
            f"diagnos. 🇧🇷 {where}: a versão {data.get('version')!r} do arquivo é mais nova que este SDK; atualize."
        )
    identity = _field(data, "identity", where)
    seed = _seed_from_b64url(_field(data, "private_key", where), source=where)
    service_account = data.get("service_account") if isinstance(data.get("service_account"), str) else None
    credential = ServiceAccountCredential(identity, seed, service_account=service_account, source=where)
    for name, expected in (("key_id", credential.key_id), ("workspace_id", credential.workspace_id)):
        if name in data and data[name] != expected:
            raise ConfigError(
                f"🇺🇸 {where}: '{name}' disagrees with 'identity'; the file was edited — download it again. "
                f"🇧🇷 {where}: '{name}' discorda de 'identity'; o arquivo foi editado — baixe de novo."
            )
    if os.name == "posix" and stat.S_IMODE(mode) & 0o077:
        warnings.warn(
            f"🇺🇸 {where} is readable by other users; run `chmod 600 {where}`. "
            f"🇧🇷 {where} é legível por outros usuários; rode `chmod 600 {where}`.",
            UserWarning,
            stacklevel=2,
        )
    return credential


@dataclass(frozen=True)
class FoundIdentity:
    """🇺🇸 What the environment named: a credential, or the legacy token. 🇧🇷 O que o ambiente nomeou."""

    credential: ServiceAccountCredential | None = None
    api_token: str | None = None


def find_identity(env: Mapping[str, str]) -> FoundIdentity:
    """🇺🇸 Apply the order in the module docstring; an empty result means nothing was configured.

    🇧🇷 Aplica a ordem da docstring do módulo; resultado vazio significa que nada foi configurado.
    """
    if env.get("DIAGNOS_CREDENTIAL"):
        return FoundIdentity(credential=ServiceAccountCredential.parse(env["DIAGNOS_CREDENTIAL"]))
    if env.get("DIAGNOS_CREDENTIALS_FILE"):
        return FoundIdentity(credential=credential_from_file(env["DIAGNOS_CREDENTIALS_FILE"]))
    if env.get("DIAGNOS_API_TOKEN"):
        return FoundIdentity(api_token=env["DIAGNOS_API_TOKEN"])
    default = default_credentials_path(env)
    if default.is_file():
        return FoundIdentity(credential=credential_from_file(default))
    return FoundIdentity()
