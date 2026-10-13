"""🇺🇸 `diagnos setup api` — the REST API as its signed container image, through Docker.

Pull the image by this installation's version, read the digest Docker
recorded, verify *that digest* with cosign, and run it by that digest: what
was checked is byte for byte what runs, so a tag moved in between cannot
slip past. An image whose signature fails is removed on the spot. Without
cosign (or with one older than `MIN_COSIGN`) the pull still happens, the
result is announced as NOT verified, and the command that verifies it is
printed alongside.

🇧🇷 `diagnos setup api` — a API REST como a imagem de container assinada dela, via Docker.

Baixar a imagem pela versão desta instalação, ler o digest que o Docker
registrou, verificar *esse digest* com o cosign, e rodá-la por esse digest:
o que foi checado é, byte a byte, o que roda, então uma tag movida no meio
do caminho não passa. Uma imagem cuja assinatura falha é removida na hora.
Sem cosign (ou com um mais velho que `MIN_COSIGN`) o download acontece mesmo
assim, o resultado é anunciado como NÃO verificado, e o comando que o
verifica é impresso junto.
"""

from __future__ import annotations

import subprocess
from typing import Final

from ..exit_codes import EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE
from ..output import Output, printable
from .environment import Environment
from .image import IMAGE, MIN_COSIGN, cosign_version, pulled_reference, run_lines, superuser, verify_argv
from .run import Plan, Step, command, shown
from .tools import INSTALL_PAGES, docker_running, find, found, missing

DEPLOY_GUIDE: Final = "https://github.com/diagnos-tech/integration/tree/develop/apps/api/deploy"


def _pin_and_verify(docker: str, cosign: str | None, tagged: str, env: Environment) -> Step:
    """🇺🇸 The step after the pull: read the digest, verify it (with cosign), print how to run it by digest.

    🇧🇷 O passo depois do download: ler o digest, verificá-lo (com cosign), imprimir como rodá-lo pelo digest.
    """
    version = env.version
    certificates = f'uvx --from "{env.requirement("dev-certs")}" diagnos-api dev-certs certs'

    def action(out: Output) -> int:
        """🇺🇸 Pins, verifies, prints the run by digest. 🇧🇷 Fixa, verifica, imprime o run pelo digest."""
        reference = pulled_reference(docker, tagged)
        if reference is None:
            out.error(f"Docker reports no single digest for {tagged} · O Docker não informa um digest único")
            return EXIT_FAILED
        if cosign is None:
            out.error(out.style("NOT verified · NÃO verificada", "yellow") + f": {reference}")
            out.error(f"  {shown(verify_argv('cosign', reference, version))}")
        elif subprocess.run(verify_argv(cosign, reference, version), stdout=subprocess.DEVNULL, check=False).returncode:  # noqa: S603
            subprocess.run([docker, "image", "rm", tagged], capture_output=True, check=False)  # noqa: S603
            out.error(
                out.style(
                    f"Signature check failed; image removed · Assinatura não confere; removida: {reference}", "red"
                )
            )
            return EXIT_FAILED
        else:
            out.line(
                out.style(f"Verified: signed by the v{version} release · Verificada: assinada pelo release", "green")
            )
        out.line(f"Certificates for a local run · Certificados para rodar local: {certificates}")
        out.line("Run it, by digest · Rode, pelo digest:")
        for line in run_lines(reference, root=superuser()):
            out.line(f"  {line}")
        return EXIT_OK

    summary = "Pin the pulled digest and verify its signature · Fixa o digest baixado e verifica a assinatura"
    return Step(summary, shown(verify_argv("cosign", f"{IMAGE}@<pulled digest>", version)), action)


def _cosign(out: Output) -> str | None:
    """🇺🇸 A cosign recent enough to trust, announced — or `None`, with why the image will not be verified.

    🇧🇷 Um cosign recente o bastante para confiar, anunciado — ou `None`, com o porquê de a imagem não ser verificada.
    """
    cosign = find("cosign")
    if cosign is None:
        out.line("cosign not found: the image will not be verified · cosign ausente: sem verificação")
        out.line(f"  {INSTALL_PAGES['cosign']}")
        return None
    installed = cosign_version(cosign)
    if installed is None or installed < MIN_COSIGN:
        wanted = ".".join(map(str, MIN_COSIGN))
        out.line(
            f"cosign older than {wanted}: the image will not be verified · cosign anterior a {wanted}: sem verificação"
        )
        return None
    found(out, "cosign", cosign)
    return cosign


def api(out: Output) -> Plan | int:
    """🇺🇸 The plan that pulls and verifies the API image; an exit code when Docker is not ready.

    🇧🇷 O plano que baixa e verifica a imagem da API; um código de saída quando o Docker não está pronto.
    """
    env = Environment.current()
    if not env.release:
        out.error(
            "No published image for a development version · Sem imagem publicada para versão de dev: "
            + printable(env.version)
        )
        return EXIT_FAILED
    docker = find("docker")
    if docker is None:
        without = f'uv tool install "{env.requirement("api")}"  (diagnos-api, no container · sem container)'
        missing(out, "docker", otherwise=without)
        return EXIT_UNAVAILABLE
    if not docker_running(docker):
        out.error("Docker is installed but not running · O Docker está instalado, mas parado.")
        out.error("  Start Docker Desktop, or · Abra o Docker Desktop, ou: sudo systemctl start docker")
        return EXIT_UNAVAILABLE
    found(out, "docker", docker)
    tagged = f"{IMAGE}:{env.version}"
    steps = (
        command(f"Pull the API image · Baixa a imagem da API ({tagged})", (docker, "pull", tagged)),
        _pin_and_verify(docker, _cosign(out), tagged, env),
    )
    return Plan("Setup · api — the REST API, as a container · a API REST, como container", steps, (DEPLOY_GUIDE,))
