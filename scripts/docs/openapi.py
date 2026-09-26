"""🇺🇸 `openapi.json`: the REST API's OpenAPI 3.1 document, exactly as FastAPI emits it (`app.openapi()`).

No envelope and no post-processing: the site reads this file as any
OpenAPI tool would, and splits `summary`/`description` with the shared
🇺🇸/🇧🇷 rule. The app is built with a placeholder vault — generating the
schema never unlocks anything, touches the network or needs a certificate.

🇧🇷 `openapi.json`: o documento OpenAPI 3.1 da API REST, exatamente como o FastAPI o emite (`app.openapi()`).

Sem envelope e sem pós-processamento: o site lê este arquivo como qualquer
ferramenta de OpenAPI leria, e divide `summary`/`description` com a regra
🇺🇸/🇧🇷 compartilhada. O app é montado com um cofre de enfeite — gerar o
schema nunca desbloqueia nada, não toca a rede nem precisa de certificado.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from diagnos import Diagnos
from diagnos_api.app import create_app
from diagnos_api.settings import ApiSettings

from .bilingual import EN_FLAG, PT_FLAG

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def build() -> dict[str, Any]:
    """🇺🇸 The OpenAPI document of `diagnos-api`, from a throwaway app instance.

    🇧🇷 O documento OpenAPI do `diagnos-api`, de uma instância descartável do app.
    """
    settings = ApiSettings(mtls_ca_file="clients-ca.pem", tls_cert_file="tls.pem", tls_key_file="tls-key.pem")
    app = create_app(settings, vault=cast(Diagnos, object()))
    return app.openapi()


def _texts(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """🇺🇸 Every `(where, text)` the site splits: info, tags, operations and their parameters.

    🇧🇷 Todo `(onde, texto)` que o site divide: info, tags, operações e seus parâmetros.
    """
    info = document.get("info", {})
    for key in ("summary", "description"):
        if key in info:
            yield f"info.{key}", info[key]
    for tag in document.get("tags", []):
        yield f"tags.{tag['name']}", tag.get("description", "")
    for path, item in document.get("paths", {}).items():
        for method in HTTP_METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            where = f"{method.upper()} {path}"
            yield f"{where} summary", operation.get("summary", "")
            yield f"{where} description", operation.get("description", "")
            for parameter in operation.get("parameters", []):
                yield f"{where} ?{parameter['name']}", parameter.get("description", "")


def untranslated(document: dict[str, Any]) -> list[str]:
    """🇺🇸 Where a text the site splits lacks a marker (or is missing): the site would show it untranslated.

    🇧🇷 Onde um texto que o site divide não tem marcador (ou falta): o site o mostraria sem tradução.
    """
    return [where for where, text in _texts(document) if EN_FLAG not in text or PT_FLAG not in text]
