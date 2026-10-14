"""SDK configuration: one immutable snapshot read once at startup.

Everything the transport needs to reach a specific vault, as a specific
service account, is here. It is deliberately not a singleton or a global:
the constructor of `VaultTransport` takes a `Settings` explicitly so that a
process can run more than one workspace at once (tests do this constantly).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from diagnos.dates import TIME_PRECISIONS, TimePrecision
from diagnos.errors import ConfigError

from .storage_hosts import DEFAULT_STORAGE_HOSTS, parse_storage_hosts
from .token import redact_api_token

DEFAULT_VAULT_URL = "https://vault.diagnos.health"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENBAO_MOUNT = "secret"
DEFAULT_OPENBAO_PATH_PREFIX = "diagnos"
_TRUE_VALUES = {"1", "true", "yes"}


def _redact_opaque(secret: str) -> str:
    """Redact a generic secret (not an `apikey-` string) for `repr`."""
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"…{tail}"


def _parse_bool(value: str) -> bool:
    """Parse an environment flag: `"1"`, `"true"` and `"yes"` (any case) are true.

    Everything else, including an empty string, is false, which matches how
    shell scripts set env flags.
    """
    return value.strip().lower() in _TRUE_VALUES


def _openbao_token(source: Mapping[str, str]) -> str | None:
    """Return `OPENBAO_TOKEN`, or the trimmed contents of the file `OPENBAO_TOKEN_FILE` names.

    A file is how Kubernetes and Docker Compose hand a process a secret
    without putting it in the environment (`/proc/<pid>/environ` is readable
    by anything running as the same user, while a mounted file can be `0400`),
    so the file form is the one the deploy manifests prefer.
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
        raise ConfigError(f"OPENBAO_TOKEN_FILE={token_file!r} could not be read.") from exc
    if not contents:
        raise ConfigError(f"OPENBAO_TOKEN_FILE={token_file!r} is empty.")
    return contents


def _parse_time_precision(raw: str | None) -> TimePrecision | None:
    """Validate `DIAGNOS_TIME_PRECISION`; unset or empty means no truncation."""
    if not raw:
        return None
    value = raw.strip().lower()
    if value not in TIME_PRECISIONS:
        raise ConfigError(f"DIAGNOS_TIME_PRECISION={raw!r} must be one of {', '.join(TIME_PRECISIONS)}.")
    return cast("TimePrecision", value)


@dataclass(frozen=True)
class Settings:
    """Immutable SDK configuration, usually built by `from_env`.

    Attributes:
        api_token: The `apikey-<jwt>` token of the service account (`DIAGNOS_API_TOKEN`).
        vault_url: The base URL of the vault (`DIAGNOS_VAULT_URL`).
        timeout_seconds: The HTTP timeout, in seconds (`DIAGNOS_TIMEOUT_SECONDS`).
        openbao_addr: The OpenBao address; setting it enables auto-unseal (`OPENBAO_ADDR`).
        openbao_token: The OpenBao token (`OPENBAO_TOKEN`, or the file named by `OPENBAO_TOKEN_FILE`).
        openbao_mount: The KV v2 mount point (`OPENBAO_MOUNT`).
        openbao_path_prefix: The path prefix under the mount (`OPENBAO_PATH_PREFIX`).
        openbao_namespace: The OpenBao namespace, if any (`OPENBAO_NAMESPACE`).
        harden_process: Whether to disable core dumps and `ptrace` attach for this process at unlock
            (`crypto/secure.py`). It is on by default because the process is about to hold clinical keys; turn it
            off only to attach a debugger (`DIAGNOS_HARDEN_PROCESS`).
        time_precision: The workspace's anonymization precision (`month`, `day`, `hour`, `minute` or `second`). The
            external API does not expose it, so set it to the workspace's value and every date is truncated before
            sealing, as the web app does (`diagnos/dates.py`). `None` writes dates as given
            (`DIAGNOS_TIME_PRECISION`).
        storage_hosts: The hosts a presigned storage URL may point at (and their subdomains), over HTTPS only; see
            `storage_hosts.py` (`DIAGNOS_STORAGE_HOSTS`).
    """

    api_token: str
    vault_url: str = DEFAULT_VAULT_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    openbao_addr: str | None = None
    openbao_token: str | None = None
    openbao_mount: str = DEFAULT_OPENBAO_MOUNT
    openbao_path_prefix: str = DEFAULT_OPENBAO_PATH_PREFIX
    openbao_namespace: str | None = None
    harden_process: bool = True
    time_precision: TimePrecision | None = None
    storage_hosts: tuple[str, ...] = DEFAULT_STORAGE_HOSTS

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> Settings:
        """Read the environment variables documented in `docs/PROTOCOL.md §11`.

        Args:
            env: The environment to read. It defaults to `os.environ` but accepts an explicit mapping so that tests
                never have to monkeypatch process-global state.

        Returns:
            The settings snapshot.

        Raises:
            ConfigError: If `DIAGNOS_API_TOKEN` is missing, `DIAGNOS_TIMEOUT_SECONDS` is not a number,
                `DIAGNOS_TIME_PRECISION` is not a valid precision, `OPENBAO_TOKEN_FILE` cannot be read or is empty,
                or `DIAGNOS_STORAGE_HOSTS` holds an entry that is not a host name.
        """
        source = env if env is not None else os.environ
        api_token = source.get("DIAGNOS_API_TOKEN")
        if not api_token:
            raise ConfigError(
                "DIAGNOS_API_TOKEN is required and was not found in the environment; "
                "set it to the 'apikey-<jwt>' token a workspace admin issued for this "
                "service account."
            )
        timeout_raw = source.get("DIAGNOS_TIMEOUT_SECONDS")
        try:
            timeout_seconds = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_SECONDS
        except ValueError as exc:
            raise ConfigError(f"DIAGNOS_TIMEOUT_SECONDS={timeout_raw!r} is not a number.") from exc
        return Settings(
            api_token=api_token,
            vault_url=source.get("DIAGNOS_VAULT_URL") or DEFAULT_VAULT_URL,
            timeout_seconds=timeout_seconds,
            openbao_addr=source.get("OPENBAO_ADDR") or None,
            openbao_token=_openbao_token(source),
            openbao_mount=source.get("OPENBAO_MOUNT") or DEFAULT_OPENBAO_MOUNT,
            openbao_path_prefix=source.get("OPENBAO_PATH_PREFIX") or DEFAULT_OPENBAO_PATH_PREFIX,
            openbao_namespace=source.get("OPENBAO_NAMESPACE") or None,
            harden_process=_parse_bool(source.get("DIAGNOS_HARDEN_PROCESS", "1")),
            time_precision=_parse_time_precision(source.get("DIAGNOS_TIME_PRECISION")),
            storage_hosts=parse_storage_hosts(source.get("DIAGNOS_STORAGE_HOSTS")),
        )

    def __repr__(self) -> str:
        """Render the settings with both tokens redacted, since each can act as this workspace or OpenBao path."""
        openbao_token = _redact_opaque(self.openbao_token) if self.openbao_token else None
        return (
            f"Settings(api_token={redact_api_token(self.api_token)!r}, vault_url={self.vault_url!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"openbao_addr={self.openbao_addr!r}, openbao_token={openbao_token!r}, "
            f"openbao_mount={self.openbao_mount!r}, openbao_path_prefix={self.openbao_path_prefix!r}, "
            f"openbao_namespace={self.openbao_namespace!r}, harden_process={self.harden_process!r}, "
            f"time_precision={self.time_precision!r}, storage_hosts={self.storage_hosts!r})"
        )
