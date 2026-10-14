"""`create_app`: wires one `Diagnos`, mTLS, error mapping and the routers into one `FastAPI`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from diagnos import Diagnos
from diagnos._version import __version__
from diagnos.api.errors import MTLS_RESPONSES, register_exception_handlers
from diagnos.api.mtls import ClientIdentity, require_client_certificate
from diagnos.api.routers import docs, exams, files, patients, session
from diagnos.api.settings import ApiSettings

logger = logging.getLogger("diagnos.api")

# One entry per router tag, in the order a reader meets them: the sections of `/docs` and of the site's API reference.
OPENAPI_TAGS = [
    {
        "name": "patients",
        "description": "Encrypted patient records: sealed in this process, versioned, never readable by the vault.",
    },
    {
        "name": "exams",
        "description": "Encrypted exams and their reports, each linked to one patient.",
    },
    {
        "name": "drives",
        "description": "Files and folders of one security group (`{sg}`), each file under its own key.",
    },
    {
        "name": "session",
        "description": "The one SDK session this process holds, and the caller's mTLS identity.",
    },
    {
        "name": "health",
        "description": "Liveness, behind mTLS like everything else.",
    },
]
DESCRIPTION = (
    "A thin HTTP face over the diagnos SDK: one process, one service account, one live session. Every route "
    "requires a client certificate signed by the CA this deployment trusts; there is no other credential. Every "
    'non-2xx response is `{"error": {"code", "message", "trace_id"}}`; branch on `code`.'
)


def _operation_id(route: APIRoute) -> str:
    """Returns the handler's own name (`list_patients`) as the OpenAPI operation id.

    The name is stable, readable and part of the site's API URLs. FastAPI's default (`list_patients_v1_patients_get`)
    repeats the path and the method, and handler names are already unique across the routers.
    """
    return route.name


def _lifespan(vault: Diagnos) -> object:
    """Builds the `lifespan` context manager that `FastAPI(...)` takes, closing over the one `vault` it manages.

    `unlock()` and `close()` run in a worker thread (`asyncio.to_thread`) because both are synchronous and `unlock()`
    can block for as long as a human takes to approve the enrollment prompt (`apps/sdk/README.md`). Running that on the
    event loop directly would freeze the whole process for the entire wait, including its ability to react to a
    shutdown signal.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Unlocks the vault on startup and closes its HTTP clients on shutdown (`Diagnos.close`, never `lock`).

        Closing rather than locking on shutdown matches `Diagnos.__exit__` (`apps/sdk/src/diagnos/client.py`): a pod
        restart means "done talking to the vault right now", not "revoke this session forever". An auto-unsealing
        deployment should resume the same session on its next start instead of being forced to re-enroll because the
        process merely exited.
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
    """Builds the `FastAPI` app: one `Diagnos`, mTLS-gated routes, uniform error bodies.

    Production never has to build a vault by hand: `vault` defaults to `Diagnos()`, which itself reads
    `diagnos.Settings.from_env()` (`apps/sdk/src/diagnos/client.py`). Tests pass a fake instead
    (`apps/api/tests/conftest.py`).

    Args:
        settings: The API's own mTLS and bind configuration.
        vault: The `Diagnos` to serve. Defaults to a new `Diagnos()` built from the environment.
        trusted_test_identity: An identity to treat as already verified, so tests can exercise routes without a real
            TLS handshake. See `mtls.require_client_certificate` for why it is never set outside of tests.

    Returns:
        The configured application; its lifespan unlocks `vault` on startup and closes it on shutdown.

    Raises:
        ConfigError: If `vault` is omitted and the SDK configuration is missing or malformed.
    """
    resolved_vault = vault if vault is not None else Diagnos()

    app = FastAPI(
        title="diagnos API",
        version=__version__,
        summary="REST facade over the diagnos SDK, authenticated by mutual TLS.",
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        generate_unique_id_function=_operation_id,
        lifespan=_lifespan(resolved_vault),  # type: ignore[arg-type]
        # FastAPI's own schema/Swagger routes skip every dependency; `routers/docs.py` serves both behind mTLS.
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.vault = resolved_vault
    app.state.trusted_test_identity = trusted_test_identity

    register_exception_handlers(app)

    app.include_router(patients.router)
    app.include_router(exams.router)
    app.include_router(files.router)
    app.include_router(session.router)
    app.include_router(docs.router)

    @app.get(
        "/healthz",
        tags=["health"],
        responses=MTLS_RESPONSES,
        summary="Liveness probe",
        description="Always mTLS-gated like every other route (`apps/api/deploy/README.md`): Kubernetes probes this "
        "process over plain TCP instead, never HTTP.",
    )
    def healthz(_identity: ClientIdentity = Depends(require_client_certificate)) -> dict[str, str]:
        """Returns a trivial 200 once the caller's certificate is verified."""
        return {"status": "ok"}

    return app
