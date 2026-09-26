"""🇺🇸 `create_app`: wires one `Diagnos`, mTLS, error mapping and the four routers into one `FastAPI`.

🇧🇷 `create_app`: conecta um `Diagnos`, o mTLS, o mapeamento de erro e os quatro roteadores num `FastAPI`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from diagnos import Diagnos
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from diagnos_api._version import __version__
from diagnos_api.errors import MTLS_RESPONSES, register_exception_handlers
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.routers import exams, files, patients, session
from diagnos_api.settings import ApiSettings

logger = logging.getLogger("diagnos_api")

# 🇺🇸 One entry per router tag, in the order a reader meets them — the sections of `/docs` and of the site's
#    API reference. Descriptions carry 🇺🇸/🇧🇷 like every summary: the site splits them with the same rule.
# 🇧🇷 Uma entrada por tag de roteador, na ordem em que quem lê as encontra — as seções do `/docs` e da
#    referência de API do site. As descrições levam 🇺🇸/🇧🇷 como todo summary: o site as divide com a mesma regra.
OPENAPI_TAGS = [
    {
        "name": "patients",
        "description": "🇺🇸 Encrypted patient records: sealed in this process, versioned, never readable by the vault. "
        "🇧🇷 Registros de paciente cifrados: selados neste processo, versionados, nunca legíveis pelo cofre.",
    },
    {
        "name": "exams",
        "description": "🇺🇸 Encrypted exams and their reports, each linked to one patient. "
        "🇧🇷 Exames cifrados e seus laudos, cada um ligado a um paciente.",
    },
    {
        "name": "drives",
        "description": "🇺🇸 Files and folders of one security group (`{sg}`), each file under its own key. "
        "🇧🇷 Arquivos e pastas de um security group (`{sg}`), cada arquivo sob a própria chave.",
    },
    {
        "name": "session",
        "description": "🇺🇸 The one SDK session this process holds, and the caller's mTLS identity. "
        "🇧🇷 A única sessão de SDK que este processo mantém, e a identidade mTLS de quem chama.",
    },
    {
        "name": "health",
        "description": "🇺🇸 Liveness, behind mTLS like everything else. 🇧🇷 Vivacidade, atrás do mTLS como todo o resto.",
    },
]
DESCRIPTION = (
    "🇺🇸 A thin HTTP face over the diagnos SDK: one process, one service account, one live session. Every route "
    "requires a client certificate signed by the CA this deployment trusts — there is no other credential. Every "
    'non-2xx response is `{"error": {"code", "message", "trace_id"}}`; branch on `code`. '
    "🇧🇷 Uma face HTTP fina sobre o SDK diagnos: um processo, uma service account, uma sessão viva. Toda rota exige "
    "um certificado de cliente assinado pela CA em que este deployment confia — não existe outra credencial. Toda "
    'resposta não-2xx é `{"error": {"code", "message", "trace_id"}}`; decida por `code`.'
)


def _operation_id(route: APIRoute) -> str:
    """🇺🇸 The handler's own name (`list_patients`) — stable, readable, and part of the site's API URLs.

    FastAPI's default (`list_patients_v1_patients_get`) repeats the path and
    the method; handler names are already unique across the four routers.

    🇧🇷 O nome do próprio handler (`list_patients`) — estável, legível, e parte das URLs de API do site.

    O padrão do FastAPI (`list_patients_v1_patients_get`) repete o caminho e
    o método; os nomes dos handlers já são únicos entre os quatro roteadores.
    """
    return route.name


def _lifespan(vault: Diagnos) -> object:
    """🇺🇸 Builds the `lifespan` context manager `FastAPI(...)` takes, closing over the one `vault` it manages.

    `unlock()`/`close()` run in a worker thread (`asyncio.to_thread`)
    because both are synchronous and `unlock()` can block for as long as a
    human takes to approve the enrollment prompt (`apps/sdk/README.md`) — running
    that on the event loop directly would freeze the whole process,
    including its ability to react to a shutdown signal, for the entire
    wait.

    🇧🇷 Constrói o gerenciador de contexto `lifespan` que `FastAPI(...)`
    recebe, fechando sobre o único `vault` que gerencia.

    `unlock()`/`close()` rodam numa thread de trabalho (`asyncio.to_thread`)
    porque os dois são síncronos e `unlock()` pode bloquear pelo tempo que
    uma pessoa levar para aprovar o prompt de enrollment (`apps/sdk/README.md`) —
    rodar isso direto no event loop congelaria o processo inteiro, incluindo
    a capacidade de reagir a um sinal de desligamento, durante toda a
    espera.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """🇺🇸 Startup unlocks the vault; shutdown closes its HTTP clients (`Diagnos.close`, never `Diagnos.lock`).

        Closing, not locking, on shutdown matches `Diagnos.__exit__`'s own
        reasoning (`apps/sdk/src/diagnos/client.py`): a pod restart is "done
        talking to the vault right now", not "revoke this session forever"
        — an auto-unsealing deployment should resume the same session on
        its next start, not be forced to re-enroll because the process
        merely exited.

        🇧🇷 A subida desbloqueia o cofre; o desligamento fecha os clients
        HTTP dele (`Diagnos.close`, nunca `Diagnos.lock`).

        Fechar, não travar, no desligamento segue o mesmo raciocínio do
        próprio `Diagnos.__exit__` (`apps/sdk/src/diagnos/client.py`): um
        reinício de pod é "terminei de falar com o cofre agora", não
        "revogue esta sessão para sempre" — um deployment com auto-unseal
        deveria retomar a mesma sessão na próxima subida, não ser forçado a
        um novo enrollment só porque o processo saiu.
        """
        logger.info("unlocking vault session")
        await asyncio.to_thread(vault.unlock)
        logger.info("vault session unlocked; serving requests")
        try:
            yield
        finally:
            logger.info("closing vault session")
            await asyncio.to_thread(vault.close)

    return lifespan


def create_app(
    settings: ApiSettings,
    vault: Diagnos | None = None,
    *,
    trusted_test_identity: ClientIdentity | None = None,
) -> FastAPI:
    """🇺🇸 Builds the `FastAPI` app: one `Diagnos`, mTLS-gated routes, uniform error bodies.

    `vault` defaults to `Diagnos()` — which itself reads `diagnos.Settings.from_env()`
    (`apps/sdk/src/diagnos/client.py`) — so production never has to build one by
    hand; tests pass a fake instead (`tests/conftest.py`). `trusted_test_identity`
    exists purely so those same tests can exercise routes without a real TLS
    handshake — see `mtls.require_client_certificate`'s docstring for why it
    is never set outside of tests.

    🇧🇷 Constrói o app `FastAPI`: um `Diagnos`, rotas travadas por mTLS,
    corpos de erro uniformes.

    `vault` usa `Diagnos()` por padrão — que por si só lê
    `diagnos.Settings.from_env()` (`apps/sdk/src/diagnos/client.py`) — para
    produção nunca precisar construir um à mão; testes passam um falso no
    lugar (`tests/conftest.py`). `trusted_test_identity` existe só para
    esses mesmos testes exercitarem rotas sem um handshake TLS de verdade —
    veja a docstring de `mtls.require_client_certificate` para o porquê de
    nunca ser setado fora de teste.
    """
    resolved_vault = vault if vault is not None else Diagnos()

    app = FastAPI(
        title="diagnos API",
        version=__version__,
        summary="🇺🇸 REST facade over the diagnos SDK, authenticated by mutual TLS. "
        "🇧🇷 Fachada REST sobre o SDK diagnos, autenticada por mTLS mútuo.",
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        generate_unique_id_function=_operation_id,
        lifespan=_lifespan(resolved_vault),  # type: ignore[arg-type]
    )
    app.state.settings = settings
    app.state.vault = resolved_vault
    app.state.trusted_test_identity = trusted_test_identity

    register_exception_handlers(app)

    app.include_router(patients.router)
    app.include_router(exams.router)
    app.include_router(files.router)
    app.include_router(session.router)

    @app.get(
        "/healthz",
        tags=["health"],
        responses=MTLS_RESPONSES,
        summary="🇺🇸 Liveness probe 🇧🇷 Sonda de vida",
        description="🇺🇸 Always mTLS-gated like every other route (`apps/api/deploy/README.md`): Kubernetes probes "
        "this process over plain TCP instead, never HTTP. "
        "🇧🇷 Sempre travado por mTLS como toda outra rota (`apps/api/deploy/README.md`): o Kubernetes sonda "
        "este processo por TCP puro, nunca por HTTP.",
    )
    def healthz(_identity: ClientIdentity = Depends(require_client_certificate)) -> dict[str, str]:
        """🇺🇸 A trivial 200 once the caller's certificate is verified.

        🇧🇷 Um 200 trivial assim que o certificado de quem chamou é verificado.
        """
        return {"status": "ok"}

    return app
