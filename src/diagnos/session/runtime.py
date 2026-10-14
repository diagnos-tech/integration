"""Describes the machine asking to enroll: the anti-phishing signal a human checks before approving.

An enrollment approval (`docs/PROTOCOL.md §5`) is granted by a person looking
at a web page, not by a cryptographic proof of "this machine should have
access." The `runtime` block is what lets that person notice "I don't
recognize this hostname, OS or cloud" before typing the approval code. It is
a description for a human, not a credential, so every field here is
best-effort and the whole function must never raise: a crash while merely
*describing* the caller would turn a benign enrollment into a hard failure.
"""

from __future__ import annotations

import getpass
import os
import platform
import socket
import sys
from pathlib import Path

# A hostname a user sets themselves rarely runs long, and a truncated one is
# still enough to recognize "yes, that's my laptop" without the field ever
# dominating the approval page's layout.
_HOSTNAME_MAX_LENGTH = 64

# The three cgroup markers that show up on every major container runtime,
# checked as substrings because the exact cgroup path format has drifted
# across cgroup v1/v2 and runtime versions.
_CONTAINER_CGROUP_MARKERS = ("docker", "containerd", "kubepods")

# One environment variable per provider is enough to say "probably this
# cloud". False positives here only cost a slightly wrong label on an
# approval page a human still has to read; there is no security decision
# riding on getting this exactly right.
_CLOUD_ENV_MARKERS: tuple[tuple[str, str], ...] = (
    ("AWS_EXECUTION_ENV", "aws"),
    ("ECS_CONTAINER_METADATA_URI", "aws"),
    ("K_SERVICE", "gcp"),
    ("GOOGLE_CLOUD_PROJECT", "gcp"),
    ("WEBSITE_INSTANCE_ID", "azure"),
    ("FLY_APP_NAME", "fly"),
    ("KUBERNETES_SERVICE_HOST", "kubernetes"),
)


def _detect_hostname() -> str | None:
    """Return a best-effort, truncated hostname, or `None` if the OS call fails."""
    try:
        hostname = socket.gethostname()
    except OSError:
        return None
    return hostname[:_HOSTNAME_MAX_LENGTH] or None


def _detect_user() -> str | None:
    """Return a best-effort OS user name; `getpass.getuser()` raises in some sandboxes with no login info."""
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — any failure here just means "no user to show"
        return None


def _detect_container() -> bool:
    """Return `True` when `/.dockerenv` or a matching `/proc/1/cgroup` marker says this runs inside a container.

    Both checks are Linux-specific and simply come back `False` on any other
    OS or if the filesystem paths cannot be read, because a container check
    that cannot decide is not evidence of anything.
    """
    try:
        if Path("/.dockerenv").exists():
            return True
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            cgroup_text = cgroup_path.read_text(errors="ignore")
            return any(marker in cgroup_text for marker in _CONTAINER_CGROUP_MARKERS)
    except OSError:
        return False
    return False


def _detect_cloud() -> str | None:
    """Return the first cloud whose marker environment variable is set, else `None`."""
    for variable, cloud_name in _CLOUD_ENV_MARKERS:
        if os.environ.get(variable):
            return cloud_name
    return None


def collect_runtime(sdk_version: str) -> dict[str, object]:
    """Build the `runtime` object `session/registry` expects (`docs/PROTOCOL.md §5`).

    Every field is collected independently and defensively; a `None` value
    is omitted rather than sent, so the shape sent on the wire always
    matches what an admin's approval page knows how to render. This
    function itself never raises, because an enrollment must not fail just
    because describing the caller's own machine hit an edge case.

    Args:
        sdk_version: The SDK version to report.

    Returns:
        The runtime description to send with the enrollment registration.
    """
    runtime: dict[str, object] = {
        "sdk_name": "diagnos-python",
        "sdk_version": sdk_version,
        "language": f"python {sys.version_info.major}.{sys.version_info.minor}",
        "os": platform.system().lower(),
        "arch": platform.machine(),
    }

    hostname = _detect_hostname()
    if hostname is not None:
        runtime["hostname"] = hostname

    user = _detect_user()
    if user is not None:
        runtime["user"] = user

    runtime["container"] = _detect_container()

    cloud = _detect_cloud()
    if cloud is not None:
        runtime["cloud"] = cloud

    return runtime
