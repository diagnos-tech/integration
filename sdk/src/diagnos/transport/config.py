"""🇺🇸 SDK configuration — one immutable snapshot read once at startup.

Everything the transport needs to reach a specific vault, as a specific
service account, is here. It is deliberately not a singleton or a global:
the constructor of `VaultTransport` takes a `Settings` explicitly so a
process can run more than one workspace at once (tests do this constantly).

🇧🇷 Configuração do SDK — um retrato imutável lido uma vez, na subida.

Tudo que o transporte precisa para falar com um cofre específico, como uma
service account específica, está aqui. De propósito não é singleton nem
global: o construtor de `VaultTransport` recebe um `Settings` explícito para
que um processo rode mais de um workspace ao mesmo tempo (os testes fazem
isso o tempo todo).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from diagnos.errors import ConfigError

from .token import redact_api_token

DEFAULT_VAULT_URL = "https://vault.diagnos.health"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENBAO_MOUNT = "secret"
DEFAULT_OPENBAO_PATH_PREFIX = "diagnos"
_TRUE_VALUES = {"1", "true", "yes"}


def _redact_opaque(secret: str) -> str:
    """🇺🇸 Generic secret redaction (not an `apikey-` string) for `repr`.

    🇧🇷 Redação genérica de segredo (não é uma string `apikey-`) para `repr`.
    """
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"…{tail}"


def _parse_bool(value: str) -> bool:
    """🇺🇸 `"1"/"true"/"yes"` (any case) are true.

    Everything else, including an empty string, is false — matches how shell
    scripts set env flags.

    🇧🇷 `"1"/"true"/"yes"` (qualquer caixa) são verdadeiro; o resto, incluindo
    string vazia, é falso — casa com o jeito que scripts de shell setam flags.
    """
    return value.strip().lower() in _TRUE_VALUES


def _openbao_token(source: Mapping[str, str]) -> str | None:
    """🇺🇸 `OPENBAO_TOKEN`, or the trimmed contents of the file `OPENBAO_TOKEN_FILE` names.

    A file is how Kubernetes and Docker Compose hand a process a secret
    without putting it in the environment (`/proc/<pid>/environ` is readable
    by anything running as the same user, a mounted file can be `0400`), so
    the file form is the one the deploy manifests prefer.

    🇧🇷 `OPENBAO_TOKEN`, ou o conteúdo (sem espaços nas pontas) do arquivo que `OPENBAO_TOKEN_FILE` nomeia.

    Um arquivo é como Kubernetes e Docker Compose entregam um segredo a um
    processo sem colocá-lo no ambiente (`/proc/<pid>/environ` é legível por
    qualquer coisa rodando como o mesmo usuário, um arquivo montado pode ser
    `0400`), então a forma em arquivo é a que os manifestos de deploy preferem.
    """
    token = source.get("OPENBAO_TOKEN")
    if token:
        return token
    token_file = source.get("OPENBAO_TOKEN_FILE")
    if not token_file:
        return None
    try:
        contents = Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigError(
            f"🇺🇸 OPENBAO_TOKEN_FILE={token_file!r} could not be read. "
            f"🇧🇷 OPENBAO_TOKEN_FILE={token_file!r} não pôde ser lido."
        ) from exc
    if not contents:
        raise ConfigError(
            f"🇺🇸 OPENBAO_TOKEN_FILE={token_file!r} is empty. 🇧🇷 OPENBAO_TOKEN_FILE={token_file!r} está vazio."
        )
    return contents


@dataclass(frozen=True)
class Settings:
    """🇺🇸 Immutable SDK configuration, usually built by `from_env`.

    🇧🇷 Configuração imutável do SDK, normalmente construída por `from_env`.
    """

    api_token: str
    vault_url: str = DEFAULT_VAULT_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    sse_c: bool = False
    openbao_addr: str | None = None
    openbao_token: str | None = None
    openbao_mount: str = DEFAULT_OPENBAO_MOUNT
    openbao_path_prefix: str = DEFAULT_OPENBAO_PATH_PREFIX
    openbao_namespace: str | None = None
    # 🇺🇸 Disable core dumps and `ptrace` attach for this process at unlock
    #    (`crypto/secure.py`). On by default: the process is about to hold
    #    clinical keys. Turn off only to attach a debugger.
    # 🇧🇷 Desliga core dumps e o attach de `ptrace` neste processo no unlock
    #    (`crypto/secure.py`). Ligado por padrão: o processo está prestes a
    #    segurar chaves clínicas. Desligue só para anexar um debugger.
    harden_process: bool = True

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> Settings:
        """🇺🇸 Read the environment variables documented in `docs/PROTOCOL.md §11`.

        `env` defaults to `os.environ` but accepts an explicit mapping so
        tests never have to monkeypatch process-global state.

        🇧🇷 Lê as variáveis de ambiente documentadas em `docs/PROTOCOL.md §11`.

        `env` usa `os.environ` por padrão, mas aceita um mapeamento explícito
        para os testes nunca precisarem de monkeypatch em estado global do
        processo.
        """
        source = env if env is not None else os.environ
        api_token = source.get("DIAGNOS_API_TOKEN")
        if not api_token:
            raise ConfigError(
                "🇺🇸 DIAGNOS_API_TOKEN is required and was not found in the environment; "
                "set it to the 'apikey-<jwt>' token a workspace admin issued for this "
                "service account. "
                "🇧🇷 DIAGNOS_API_TOKEN é obrigatório e não foi encontrado no ambiente; "
                "defina como o token 'apikey-<jwt>' que um admin do workspace emitiu "
                "para esta service account."
            )
        timeout_raw = source.get("DIAGNOS_TIMEOUT_SECONDS")
        try:
            timeout_seconds = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_SECONDS
        except ValueError as exc:
            raise ConfigError(
                f"🇺🇸 DIAGNOS_TIMEOUT_SECONDS={timeout_raw!r} is not a number. "
                f"🇧🇷 DIAGNOS_TIMEOUT_SECONDS={timeout_raw!r} não é um número."
            ) from exc
        return Settings(
            api_token=api_token,
            vault_url=source.get("DIAGNOS_VAULT_URL") or DEFAULT_VAULT_URL,
            timeout_seconds=timeout_seconds,
            sse_c=_parse_bool(source.get("DIAGNOS_SSE_C", "")),
            openbao_addr=source.get("OPENBAO_ADDR") or None,
            openbao_token=_openbao_token(source),
            openbao_mount=source.get("OPENBAO_MOUNT") or DEFAULT_OPENBAO_MOUNT,
            openbao_path_prefix=source.get("OPENBAO_PATH_PREFIX") or DEFAULT_OPENBAO_PATH_PREFIX,
            openbao_namespace=source.get("OPENBAO_NAMESPACE") or None,
            harden_process=_parse_bool(source.get("DIAGNOS_HARDEN_PROCESS", "1")),
        )

    def __repr__(self) -> str:
        """🇺🇸 Redacted: both tokens are capable of acting as this workspace / OpenBao path.

        🇧🇷 Redigido: os dois tokens são capazes de agir como este workspace / path do OpenBao.
        """
        openbao_token = _redact_opaque(self.openbao_token) if self.openbao_token else None
        return (
            f"Settings(api_token={redact_api_token(self.api_token)!r}, vault_url={self.vault_url!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, sse_c={self.sse_c!r}, "
            f"openbao_addr={self.openbao_addr!r}, openbao_token={openbao_token!r}, "
            f"openbao_mount={self.openbao_mount!r}, openbao_path_prefix={self.openbao_path_prefix!r}, "
            f"openbao_namespace={self.openbao_namespace!r}, harden_process={self.harden_process!r})"
        )
