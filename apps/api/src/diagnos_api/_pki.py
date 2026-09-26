"""🇺🇸 The X.509 work behind `dev-certs`: one CA, then leaves it signs. Imported only by that command.

EC P-256 keys (fast to generate, accepted by every TLS stack uvicorn runs
on), SHA-256 signatures, a five-minute back-dated start for clock skew, and
the extensions a strict client checks: `BasicConstraints` and `KeyUsage` on
the CA, `ExtendedKeyUsage` on each leaf, `SubjectAlternativeName` on the
server — modern clients ignore the CN for host names.

🇧🇷 O trabalho X.509 por trás do `dev-certs`: uma CA, depois as folhas que ela assina. Importado só por esse comando.

Chaves EC P-256 (rápidas de gerar, aceitas por toda pilha TLS em que o
uvicorn roda), assinaturas SHA-256, início recuado em cinco minutos por
causa de relógio defasado, e as extensões que um cliente estrito confere:
`BasicConstraints` e `KeyUsage` na CA, `ExtendedKeyUsage` em cada folha,
`SubjectAlternativeName` no servidor — clientes modernos ignoram o CN para
nomes de host.
"""

from __future__ import annotations

import datetime
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

Issued = tuple[ec.EllipticCurvePrivateKey, x509.Certificate]


def issue_ca(common_name: str, *, days: int) -> Issued:
    """🇺🇸 A self-signed CA that may sign leaves only (`path_length=0`).

    🇧🇷 Uma CA autoassinada que só pode assinar folhas (`path_length=0`).
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = _name(common_name)
    usage = x509.KeyUsage(
        digital_signature=False,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=True,
        encipher_only=False,
        decipher_only=False,
    )
    certificate = (
        _builder(name, name, key, days)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(usage, critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, certificate


def issue_server(ca: Issued, *, days: int) -> Issued:
    """🇺🇸 A server leaf valid for `localhost`, `127.0.0.1` and `::1`.

    🇧🇷 Uma folha de servidor válida para `localhost`, `127.0.0.1` e `::1`.
    """
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    return _leaf(ca, "localhost", ExtendedKeyUsageOID.SERVER_AUTH, days, x509.SubjectAlternativeName(names))


def issue_client(ca: Issued, common_name: str, *, days: int) -> Issued:
    """🇺🇸 A client leaf; its CN is what `DIAGNOS_API_ALLOWED_CLIENT_CN` matches.

    🇧🇷 Uma folha de cliente; o CN dela é o que `DIAGNOS_API_ALLOWED_CLIENT_CN` compara.
    """
    return _leaf(ca, common_name, ExtendedKeyUsageOID.CLIENT_AUTH, days, None)


def certificate_pem(certificate: x509.Certificate) -> bytes:
    """🇺🇸 PEM of a certificate. 🇧🇷 PEM de um certificado."""
    return certificate.public_bytes(serialization.Encoding.PEM)


def key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    """🇺🇸 Unencrypted PKCS#8 PEM — uvicorn reads it without a passphrase prompt.

    🇧🇷 PEM PKCS#8 sem cifra — o uvicorn o lê sem pedir senha.
    """
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _leaf(
    ca: Issued,
    common_name: str,
    usage: x509.ObjectIdentifier,
    days: int,
    names: x509.SubjectAlternativeName | None,
) -> Issued:
    """🇺🇸 A key and a certificate the CA signs. 🇧🇷 Uma chave e um certificado que a CA assina."""
    ca_key, ca_certificate = ca
    key = ec.generate_private_key(ec.SECP256R1())
    builder = _builder(_name(common_name), ca_certificate.subject, key, days).add_extension(
        x509.ExtendedKeyUsage([usage]), critical=False
    )
    if names is not None:
        builder = builder.add_extension(names, critical=False)
    return key, builder.sign(ca_key, hashes.SHA256())


def _builder(
    subject: x509.Name, issuer: x509.Name, key: ec.EllipticCurvePrivateKey, days: int
) -> x509.CertificateBuilder:
    """🇺🇸 The fields every certificate here shares. 🇧🇷 Os campos que todo certificado daqui compartilha."""
    now = datetime.datetime.now(datetime.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=days))
    )


def _name(common_name: str) -> x509.Name:
    """🇺🇸 A subject with only a CN. 🇧🇷 Um subject só com CN."""
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
