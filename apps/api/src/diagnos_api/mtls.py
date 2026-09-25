"""🇺🇸 Mutual TLS: the API's one and only authentication mechanism.

A password or a bearer token can leak — copied into a chat, committed by
accident, replayed from a stolen log. A client certificate signed by a CA
this deployment chose to trust cannot be reproduced from a leaked secret
alone: the caller has to hold the private key the CA signed, which never
travels over the wire at all. That is why this API never accepts
`Authorization` headers, API keys, or `X-Forwarded-*` identity from a
reverse proxy — a proxy header is just a string an attacker who reached the
proxy can set to whatever they like, while the TLS client certificate is
the one thing on the request that uvicorn itself verified cryptographically
before a single byte of application code ran. `ssl_config_for_uvicorn`
configures that verification (`ssl.CERT_REQUIRED`); `ClientCertH11Protocol`
carries the verified certificate from uvicorn's connection object into the
ASGI request every route depends on; `require_client_certificate` turns it
into the `ClientIdentity` a route can trust.

🇧🇷 mTLS: o único e exclusivo mecanismo de autenticação da API.

Uma senha ou um bearer token pode vazar — copiado num chat, commitado por
acidente, reproduzido de um log roubado. Um certificado de cliente assinado
por uma CA que este deployment escolheu confiar não pode ser reproduzido só
a partir de um segredo vazado: quem chama precisa ter a chave privada que a
CA assinou, que nunca viaja pela rede. É por isso que esta API nunca aceita
header `Authorization`, API key, nem identidade `X-Forwarded-*` de um proxy
reverso — um header de proxy é só uma string que um atacante que alcançou o
proxy pode setar para o que quiser, enquanto o certificado de cliente TLS é
a única coisa na requisição que o próprio uvicorn já verificou
criptograficamente antes de qualquer byte de código de aplicação rodar.
`ssl_config_for_uvicorn` configura essa verificação (`ssl.CERT_REQUIRED`);
`ClientCertH11Protocol` carrega o certificado verificado da conexão do
uvicorn até a requisição ASGI da qual toda rota depende;
`require_client_certificate` o transforma na `ClientIdentity` em que uma
rota pode confiar.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from uvicorn.protocols.http.h11_impl import H11Protocol

from diagnos_api.settings import ApiSettings


@dataclass(frozen=True)
class ClientIdentity:
    """🇺🇸 Who is calling: the verified subject of the client certificate uvicorn accepted for this connection.

    🇧🇷 Quem está chamando: o subject verificado do certificado de cliente que o uvicorn aceitou nesta conexão.
    """

    common_name: str
    serial: str


def ssl_config_for_uvicorn(settings: ApiSettings) -> dict[str, Any]:
    """🇺🇸 The `ssl_*` keyword arguments `uvicorn.run`/`uvicorn.Config` need to require a client certificate.

    `ssl_cert_reqs=ssl.CERT_REQUIRED` is what makes the handshake itself
    refuse a connection that never presents a certificate signed by
    `ssl_ca_certs` — a request without one never becomes an HTTP request at
    all, so `require_client_certificate` below only ever has to interpret a
    certificate that already passed chain verification, never decide
    whether one was required.

    🇧🇷 Os argumentos nomeados `ssl_*` que `uvicorn.run`/`uvicorn.Config`
    precisam para exigir um certificado de cliente.

    `ssl_cert_reqs=ssl.CERT_REQUIRED` é o que faz o próprio handshake
    recusar uma conexão que nunca apresenta um certificado assinado por
    `ssl_ca_certs` — uma requisição sem um nunca vira uma requisição HTTP,
    então `require_client_certificate` abaixo só precisa interpretar um
    certificado que já passou pela verificação de cadeia, nunca decidir se
    um era exigido.
    """
    return {
        "ssl_certfile": settings.tls_cert_file,
        "ssl_keyfile": settings.tls_key_file,
        "ssl_ca_certs": settings.mtls_ca_file,
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }


class ClientCertH11Protocol(H11Protocol):
    """🇺🇸 uvicorn's HTTP/1.1 protocol, patched to carry the raw connection into the ASGI scope.

    Plain uvicorn never puts the `asyncio.Transport` of a connection into the
    ASGI `scope` it hands the application — there is no ASGI-standard way to
    reach `ssl_object.getpeercert()` from inside a route otherwise. Every
    place in `H11Protocol` that starts a request assigns a brand new dict to
    `self.scope`; overriding `scope` as a property, rather than duplicating
    that request-parsing logic, means this class tracks upstream uvicorn
    without modification as long as that one assignment keeps existing.
    Pass this class as `uvicorn.run(..., http=ClientCertH11Protocol)` — it is
    the only way `require_client_certificate` ever finds a certificate in
    production; `create_app`'s `trusted_test_identity` is what tests use
    instead, since `TestClient` never runs a real TLS handshake at all.

    🇧🇷 O protocolo HTTP/1.1 do uvicorn, remendado para carregar a conexão
    crua até o scope ASGI.

    O uvicorn puro nunca coloca o `asyncio.Transport` de uma conexão no
    `scope` ASGI que entrega à aplicação — não existe um jeito padrão-ASGI de
    alcançar `ssl_object.getpeercert()` de dentro de uma rota de outro jeito.
    Todo lugar em `H11Protocol` que inicia uma requisição atribui um dict novo
    a `self.scope`; sobrescrever `scope` como property, em vez de duplicar
    essa lógica de parsing de requisição, faz esta classe acompanhar o
    uvicorn upstream sem modificação enquanto essa única atribuição continuar
    existindo. Passe esta classe como `uvicorn.run(..., http=ClientCertH11Protocol)`
    — é o único jeito de `require_client_certificate` achar um certificado em
    produção; o `trusted_test_identity` de `create_app` é o que os testes
    usam no lugar, já que o `TestClient` nunca faz um handshake TLS de
    verdade.
    """

    # mypy flags this whole property/setter pair against the third-party
    # base class's plain instance attribute (`self.scope: HTTPScope = None`
    # in `H11Protocol.__init__`) — narrowing that attribute into a property
    # is exactly the point of this class, and the runtime behavior (still a
    # settable `self.scope`) is exactly what `H11Protocol` expects.
    # mypy assinala este par property/setter inteiro contra o atributo de
    # instância simples da classe base de terceiros (`self.scope: HTTPScope
    # = None` em `H11Protocol.__init__`) — restringir esse atributo a uma
    # property é exatamente o ponto desta classe, e o comportamento em
    # tempo de execução (ainda um `self.scope` atribuível) é exatamente o
    # que `H11Protocol` espera.
    @property  # type: ignore[override]
    def scope(self) -> dict[str, Any] | None:
        """🇺🇸 The ASGI scope for the request currently being parsed, or `None` between requests.

        🇧🇷 O scope ASGI da requisição sendo interpretada agora, ou `None` entre requisições.
        """
        return self.__dict__.get("_client_cert_scope")

    @scope.setter
    def scope(self, value: dict[str, Any] | None) -> None:
        """🇺🇸 Stamps `transport` onto every new scope so it survives into the ASGI request.

        🇧🇷 Carimba `transport` em todo scope novo para ele sobreviver até a requisição ASGI.
        """
        if value is not None:
            value["transport"] = self.transport
        self.__dict__["_client_cert_scope"] = value


def _common_name(cert: dict[str, Any]) -> str | None:
    """🇺🇸 The certificate's `commonName`, from `ssl.SSLObject.getpeercert()`'s nested RDN tuples.

    🇧🇷 O `commonName` do certificado, das tuplas de RDN aninhadas de `ssl.SSLObject.getpeercert()`.
    """
    for rdn in cert.get("subject", ()):
        for key, value in rdn:
            if key == "commonName":
                return str(value)
    return None


def _identity_from_request(request: Request) -> ClientIdentity | None:
    """🇺🇸 Reads the peer certificate `ClientCertH11Protocol` attached to this connection, if any.

    🇧🇷 Lê o certificado do par que `ClientCertH11Protocol` anexou a esta conexão, se houver.
    """
    transport = request.scope.get("transport")
    if transport is None:
        return None
    ssl_object = transport.get_extra_info("ssl_object")
    if ssl_object is None:
        return None
    cert = ssl_object.getpeercert()
    if not cert:
        return None
    common_name = _common_name(cert)
    if common_name is None:
        return None
    return ClientIdentity(common_name=common_name, serial=str(cert.get("serialNumber", "")))


async def require_client_certificate(request: Request) -> ClientIdentity:
    """🇺🇸 FastAPI dependency: the caller's verified identity, or a 401/403 before any route body runs.

    `request.app.state.trusted_test_identity` is the one deliberate escape
    hatch — set only by `create_app` in tests (`conftest.py`), never in
    production, because `TestClient` talks ASGI-in-process and never
    negotiates real TLS. Every other caller has to have come through
    `ClientCertH11Protocol` over an actual mTLS connection.

    🇧🇷 Dependência do FastAPI: a identidade verificada de quem chama, ou um
    401/403 antes de qualquer corpo de rota rodar.

    `request.app.state.trusted_test_identity` é a única válvula de escape
    deliberada — setada só por `create_app` em teste (`conftest.py`), nunca
    em produção, porque o `TestClient` fala ASGI dentro do processo e nunca
    negocia TLS de verdade. Todo outro chamador precisa ter vindo por
    `ClientCertH11Protocol` numa conexão mTLS de verdade.
    """
    trusted_test_identity: ClientIdentity | None = getattr(request.app.state, "trusted_test_identity", None)
    identity = trusted_test_identity if trusted_test_identity is not None else _identity_from_request(request)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "client_certificate_required",
                    "message": "🇺🇸 no client certificate was presented for this connection. "
                    "🇧🇷 nenhum certificado de cliente foi apresentado nesta conexão.",
                    "trace_id": None,
                }
            },
        )
    settings: ApiSettings = request.app.state.settings
    if settings.allowed_client_cns and identity.common_name not in settings.allowed_client_cns:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "client_certificate_cn_not_allowed",
                    "message": f"🇺🇸 client certificate CN {identity.common_name!r} is not in the allowed list. "
                    f"🇧🇷 o CN {identity.common_name!r} do certificado de cliente não está na lista permitida.",
                    "trace_id": None,
                }
            },
        )
    return identity
