"""Where ciphertext may go: the object-storage hosts the SDK accepts in a presigned URL from the vault.

The vault hands out presigned URLs, and the SDK then sends sealed bytes (and,
for files, the SSE-C key) straight to that URL. Everything is already
end-to-end encrypted, so this is defense in depth, not the lock itself: a
misconfigured or compromised vault still cannot get plaintext, but it also
cannot quietly point uploads at a host nobody chose. An entry matches the
host itself and any subdomain, over HTTPS only.

The defaults are the diagnos user-content domain and the R2 endpoint the
vault presigns against today. `DIAGNOS_STORAGE_HOSTS` replaces them, for
example for a self-hosted vault or a staging bucket.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final
from urllib.parse import urlsplit

from diagnos.errors import ConfigError, ProtocolError

DEFAULT_STORAGE_HOSTS: Final[tuple[str, ...]] = ("diagnosusercontent.com", "r2.cloudflarestorage.com")

_HOSTNAME = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


def parse_storage_hosts(raw: str | None) -> tuple[str, ...]:
    """Normalize the value of `DIAGNOS_STORAGE_HOSTS` into a tuple of hosts.

    The value is comma- or space-separated. A leading `*.` or `.` is accepted
    and dropped, since every entry already covers its subdomains.

    Args:
        raw: The raw environment value. `None` or blank keeps the defaults.

    Returns:
        The lowercase, de-duplicated hosts, in order.

    Raises:
        ConfigError: If an entry is not a valid host name.
    """
    if raw is None or not raw.strip():
        return DEFAULT_STORAGE_HOSTS
    hosts: list[str] = []
    for token in re.split(r"[,\s]+", raw.strip()):
        host = token.lower().removeprefix("*.").strip(".")
        if not _HOSTNAME.match(host):
            raise ConfigError(f"DIAGNOS_STORAGE_HOSTS has an entry that is not a host name: {token!r}.")
        if host not in hosts:
            hosts.append(host)
    return tuple(hosts)


def storage_host_allowed(url: str, hosts: Iterable[str]) -> bool:
    """Return whether `url` is HTTPS on one of `hosts` or a subdomain of one, never a mere suffix like `evil-x.com`.

    Args:
        url: The presigned URL to check.
        hosts: The allowed hosts.

    Returns:
        `True` if the URL may be used.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in hosts)


def require_storage_host(url: str, hosts: tuple[str, ...]) -> None:
    """Refuse, before a single byte leaves, a storage URL outside `hosts`.

    Args:
        url: The presigned URL to check.
        hosts: The allowed hosts.

    Raises:
        ProtocolError: If the URL is not HTTPS on an allowed host.
    """
    if storage_host_allowed(url, hosts):
        return
    host = urlsplit(url).hostname or url
    raise ProtocolError(
        f"the vault handed a storage URL on {host!r}, which is not HTTPS on an allowed host "
        f"({', '.join(hosts)}); add it to DIAGNOS_STORAGE_HOSTS if you trust it."
    )
