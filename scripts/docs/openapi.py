"""`openapi.json`: the REST API's OpenAPI 3.1 document, exactly as FastAPI emits it (`app.openapi()`).

No envelope and no post-processing: the site reads this file as any OpenAPI
tool would, and handles `summary`/`description` itself — plain English text
reaches both locales unchanged (see `l10n`). The app is built with a
placeholder vault — generating the schema never unlocks anything, touches
the network or needs a certificate.
"""

from __future__ import annotations

from typing import Any, cast

from diagnos import Diagnos
from diagnos.api.app import create_app
from diagnos.api.settings import ApiSettings

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def build() -> dict[str, Any]:
    """Returns the OpenAPI document of `diagnos-api`, from a throwaway app instance."""
    settings = ApiSettings(mtls_ca_file="clients-ca.pem", tls_cert_file="tls.pem", tls_key_file="tls-key.pem")
    app = create_app(settings, vault=cast(Diagnos, object()))
    return app.openapi()
