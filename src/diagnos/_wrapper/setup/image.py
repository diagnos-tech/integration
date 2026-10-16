"""🇺🇸 Trusting the API image: which digest Docker pulled, and whether the release workflow signed exactly that.

Everything that ends up in an argv here is either a constant or matched
against a strict pattern first — the version (`_version.RELEASE`), the
pulled reference (`IMAGE@sha256:<64 hex>`) — so nothing Docker or the environment
says can smuggle an option or a second image into a command. The accepted
signer is a single identity: `release.yml` in this repository, run by the
push of the tag of this exact version, through GitHub's OIDC issuer.

🇧🇷 Confiar na imagem da API: qual digest o Docker baixou, e se o workflow de release assinou exatamente esse.

Tudo que acaba num argv aqui é uma constante ou é comparado antes com um
padrão estrito — a versão (`_version.RELEASE`), a referência baixada
(`IMAGE@sha256:<64 hex>`) — então nada que o Docker ou o ambiente digam
consegue contrabandear uma opção ou uma segunda imagem para um comando. O
assinante aceito é uma identidade só: o `release.yml` deste repositório,
rodado pelo push da tag desta versão exata, pelo emissor OIDC do GitHub.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Final

IMAGE: Final = "ghcr.io/diagnos-tech/diagnos-api"
ISSUER: Final = "https://token.actions.githubusercontent.com"
WORKFLOW: Final = "https://github.com/diagnos-tech/integration/.github/workflows/release.yml"
# 🇺🇸 Releases run on a tag push only; a manual run of the same workflow at the same tag is not a release.
# 🇧🇷 Releases rodam só no push de uma tag; uma execução manual do mesmo workflow na mesma tag não é release.
TRIGGER: Final = "push"
# 🇺🇸 The image's own user (`Dockerfile`), which owns the certificates when root sets them up.
# 🇧🇷 O usuário da própria imagem (`Dockerfile`), dono dos certificados quando o root os prepara.
IMAGE_USER: Final = "10001:10001"
# 🇺🇸 cosign 3.1.3 fixed a verification bypass (GHSA-fx35-mq7g-6g98); an older one is not trusted to say "verified".
# 🇧🇷 O cosign 3.1.3 corrigiu um desvio de verificação (GHSA-fx35-mq7g-6g98); um mais velho não é confiável para isso.
MIN_COSIGN: Final = (3, 1, 3)
_PINNED: Final = re.compile(rf"{re.escape(IMAGE)}@sha256:[0-9a-f]{{64}}")
_COSIGN_VERSION: Final = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def identity(version: str) -> str:
    """🇺🇸 The only signer accepted: the release workflow, run for tag `v<version>`.

    🇧🇷 O único assinante aceito: o workflow de release, rodado para a tag `v<versão>`.
    """
    return f"{WORKFLOW}@refs/tags/v{version}"


def verify_argv(cosign: str, reference: str, version: str) -> tuple[str, ...]:
    """🇺🇸 `cosign verify` of `reference`, pinned to the release identity, its trigger and GitHub's issuer.

    🇧🇷 `cosign verify` de `reference`, preso à identidade do release, ao gatilho dela e ao emissor do GitHub.
    """
    return (
        cosign,
        "verify",
        "--certificate-identity",
        identity(version),
        "--certificate-oidc-issuer",
        ISSUER,
        "--certificate-github-workflow-trigger",
        TRIGGER,
        reference,
    )


def pulled_reference(docker: str, tagged: str) -> str | None:
    """🇺🇸 `IMAGE@sha256:…` Docker recorded when it pulled `tagged`; `None` unless exactly one is well formed.

    🇧🇷 O `IMAGE@sha256:…` que o Docker registrou ao baixar `tagged`; `None` salvo se exatamente um for bem formado.
    """
    result = subprocess.run(  # noqa: S603 — argv list, absolute path from `find`
        [docker, "image", "inspect", "--format", "{{json .RepoDigests}}", tagged],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        recorded = json.loads(result.stdout) if result.returncode == 0 else []
    except ValueError:
        return None
    pinned = {entry for entry in recorded if isinstance(entry, str) and _PINNED.fullmatch(entry)}
    return pinned.pop() if len(pinned) == 1 else None


def cosign_version(cosign: str) -> tuple[int, int, int] | None:
    """🇺🇸 `(major, minor, patch)` of the installed cosign, or `None` when it cannot say.

    🇧🇷 `(maior, menor, patch)` do cosign instalado, ou `None` quando ele não consegue dizer.
    """
    result = subprocess.run(  # noqa: S603 — argv list, absolute path from `find`
        [cosign, "version", "--json"], capture_output=True, text=True, check=False
    )
    try:
        reported = json.loads(result.stdout).get("gitVersion", "") if result.returncode == 0 else ""
    except (ValueError, AttributeError):
        return None
    match = _COSIGN_VERSION.match(reported) if isinstance(reported, str) else None
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def superuser() -> bool:
    """🇺🇸 Whether this process runs as root (never on Windows).

    🇧🇷 Se este processo roda como root (nunca no Windows).
    """
    return sys.platform != "win32" and os.geteuid() == 0


def run_lines(reference: str, *, root: bool = False) -> tuple[str, ...]:
    """🇺🇸 A hardened `docker run` of `reference`, by digest: read-only, no capabilities, loopback only.

    Memory locking comes from `--ulimit memlock`: under `no-new-privileges`
    the kernel ignores the image's file capability. `--user` matches the
    owner of the certificates `dev-certs` writes with mode `0600` — except
    for `root`, whose certificates are handed to the image's own user
    instead, so the container never runs as root.

    🇧🇷 Um `docker run` endurecido de `reference`, pelo digest: só leitura, sem capabilities, só loopback.

    O travamento de memória vem do `--ulimit memlock`: sob `no-new-privileges`
    o kernel ignora a capability de arquivo da imagem. O `--user` casa com o
    dono dos certificados que o `dev-certs` grava com modo `0600` — salvo
    para o `root`, cujos certificados passam ao usuário da própria imagem,
    para o container nunca rodar como root.
    """
    user = f"chown -R {IMAGE_USER} certs && " if root else ""
    flags = "" if root else ' --user "$(id -u):$(id -g)"'
    return (
        f"{user}docker run --rm --read-only --tmpfs /tmp --cap-drop ALL{flags} \\",
        "  --security-opt no-new-privileges:true --ulimit memlock=-1:-1 -p 127.0.0.1:8443:8443 \\",
        "  -e DIAGNOS_TOKEN -e DIAGNOS_API_MTLS_CA_FILE=/certs/ca.pem \\",
        "  -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \\",
        f'  -v "$PWD/certs:/certs:ro" {reference}',
    )
