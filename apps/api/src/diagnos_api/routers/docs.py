"""🇺🇸 `/openapi.json` and `/docs`, behind the same client certificate as every other route.

FastAPI mounts its own schema and Swagger routes as plain Starlette routes,
which no FastAPI dependency reaches — not even app-level `dependencies=`.
`create_app` switches those off and mounts these instead, so the schema is
not a map of the API for anyone who reached the port with a certificate
from the right CA but a CN outside `DIAGNOS_API_ALLOWED_CLIENT_CN`.

🇧🇷 `/openapi.json` e `/docs`, atrás do mesmo certificado de cliente de toda outra rota.

O FastAPI monta as próprias rotas de schema e de Swagger como rotas
Starlette puras, que nenhuma dependência do FastAPI alcança — nem as
`dependencies=` do app. `create_app` desliga essas e monta estas no lugar,
para o schema não ser um mapa da API para quem chegou à porta com um
certificado da CA certa mas um CN fora de `DIAGNOS_API_ALLOWED_CLIENT_CN`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from diagnos_api.mtls import ClientIdentity, require_client_certificate

OPENAPI_URL = "/openapi.json"

router = APIRouter(include_in_schema=False)


@router.get(OPENAPI_URL)
def openapi_schema(request: Request, _identity: ClientIdentity = Depends(require_client_certificate)) -> JSONResponse:
    """🇺🇸 The generated OpenAPI document. 🇧🇷 O documento OpenAPI gerado."""
    return JSONResponse(request.app.openapi())


@router.get("/docs")
def swagger_ui(_identity: ClientIdentity = Depends(require_client_certificate)) -> HTMLResponse:
    """🇺🇸 Swagger UI over `/openapi.json`. 🇧🇷 Swagger UI sobre `/openapi.json`."""
    return get_swagger_ui_html(openapi_url=OPENAPI_URL, title="diagnos API")
