"""🇺🇸 Describes the machine asking to enroll — the anti-phishing signal a human checks before approving.

An enrollment approval (`docs/PROTOCOL.md §5`) is granted by a person looking
at a web page, not by a cryptographic proof of "this machine should have
access." The `runtime` block is what lets that person notice "I don't
recognize this hostname/OS/cloud" before typing the approval code — it is a
description for a human, not a credential, so every field here is
best-effort and the whole function must never raise: a crash while merely
*describing* the caller would turn a benign enrollment into a hard failure.

🇧🇷 Descreve a máquina que pede para se registrar — o sinal anti-phishing que
uma pessoa confere antes de aprovar.

Uma aprovação de enrollment (`docs/PROTOCOL.md §5`) é concedida por uma
pessoa olhando uma página web, não por uma prova criptográfica de "esta
máquina deveria ter acesso". O bloco `runtime` é o que deixa essa pessoa
notar "não reconheço este hostname/SO/cloud" antes de digitar o código de
aprovação — é uma descrição para humano, não uma credencial, então todo
campo aqui é best-effort e a função inteira nunca pode lançar: uma quebra só
por *descrever* quem está chamando transformaria um enrollment inofensivo
numa falha dura.
"""

from __future__ import annotations

import getpass
import os
import platform
import socket
import sys
from pathlib import Path

# 🇺🇸 A hostname a user sets themselves rarely runs long; a truncated one is
# still enough to recognize "yes, that's my laptop" without the field ever
# dominating the approval page's layout.
# 🇧🇷 Um hostname que a pessoa mesma define raramente é longo; um truncado
# ainda basta para reconhecer "sim, é o meu notebook" sem o campo dominar o
# layout da página de aprovação.
_HOSTNAME_MAX_LENGTH = 64

# 🇺🇸 The three cgroup markers that show up on every major container runtime;
# checked as substrings because the exact cgroup path format has drifted
# across cgroup v1/v2 and runtime versions.
# 🇧🇷 Os três marcadores de cgroup que aparecem em todo runtime de container
# relevante; conferidos como substring porque o formato exato do caminho de
# cgroup mudou entre cgroup v1/v2 e versões de runtime.
_CONTAINER_CGROUP_MARKERS = ("docker", "containerd", "kubepods")

# 🇺🇸 One environment variable per provider is enough to say "probably this
# cloud" — false positives here only cost a slightly wrong label on an
# approval page a human still has to read; there is no security decision
# riding on getting this exactly right.
# 🇧🇷 Uma variável de ambiente por provedor basta para dizer "provavelmente
# esta nuvem" — falsos positivos aqui só custam um rótulo um pouco errado
# numa página que uma pessoa ainda vai ler; nenhuma decisão de segurança
# depende de acertar isto com exatidão.
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
    """🇺🇸 Best-effort, truncated hostname; `None` if the OS call fails.

    🇧🇷 Hostname best-effort, truncado; `None` se a chamada ao SO falhar.
    """
    try:
        hostname = socket.gethostname()
    except OSError:
        return None
    return hostname[:_HOSTNAME_MAX_LENGTH] or None


def _detect_user() -> str | None:
    """🇺🇸 Best-effort OS user name; `getpass.getuser()` raises in some sandboxes with no login info.

    🇧🇷 Nome de usuário do SO best-effort; `getpass.getuser()` lança em
    alguns sandboxes sem informação de login.
    """
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — any failure here just means "no user to show"
        return None


def _detect_container() -> bool:
    """🇺🇸 `/.dockerenv` or a matching `/proc/1/cgroup` marker means "running inside a container".

    Both checks are Linux-specific and simply come back `False` on any other
    OS or if the filesystem paths cannot be read — a container check that
    cannot decide is not evidence of anything.

    🇧🇷 `/.dockerenv` ou um marcador correspondente em `/proc/1/cgroup`
    significa "rodando dentro de um container".

    As duas checagens são específicas de Linux e simplesmente voltam `False`
    em qualquer outro SO ou se os caminhos não puderem ser lidos — uma
    checagem de container que não consegue decidir não é evidência de nada.
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
    """🇺🇸 The first cloud whose marker environment variable is set, else `None`.

    🇧🇷 A primeira nuvem cuja variável de ambiente marcadora está definida, senão `None`.
    """
    for variable, cloud_name in _CLOUD_ENV_MARKERS:
        if os.environ.get(variable):
            return cloud_name
    return None


def collect_runtime(sdk_version: str) -> dict[str, object]:
    """🇺🇸 The `runtime` object `session/registry` expects (`docs/PROTOCOL.md §5`).

    Every field is collected independently and defensively; a `None` value
    is omitted rather than sent, so the shape sent on the wire always
    matches what an admin's approval page knows how to render. This
    function itself never raises — an enrollment must not fail just because
    describing the caller's own machine hit an edge case.

    🇧🇷 O objeto `runtime` que `session/registry` espera (`docs/PROTOCOL.md §5`).

    Todo campo é coletado de forma independente e defensiva; um valor `None`
    é omitido em vez de enviado, para a forma que vai no fio sempre bater
    com o que a página de aprovação de um admin sabe renderizar. Esta função
    nunca lança — um enrollment não pode falhar só porque descrever a
    própria máquina de quem chama bateu num caso extremo.
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
