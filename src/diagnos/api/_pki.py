"""The X.509 work behind `dev-certs`: one CA, then the leaves it signs. Imported only by that command.

Keys are EC P-256 (fast to generate, accepted by every TLS stack uvicorn runs on) and signatures are SHA-256. Each
certificate starts five minutes in the past to tolerate clock skew, and carries the extensions a strict client checks:
`BasicConstraints` and `KeyUsage` on the CA, `ExtendedKeyUsage` on each leaf, `SubjectAlternativeName` on the server
(modern clients ignore the CN for host names), and the key identifiers, `SubjectKeyIdentifier` on every certificate and
`AuthorityKeyIdentifier` on each leaf. Python 3.13's default TLS context is strict (`VERIFY_X509_STRICT`) and refuses a
chain without them.
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
    """Issues a self-signed CA that may sign leaves only (`path_length=0`)."""
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
    """Issues a server leaf valid for `localhost`, `127.0.0.1` and `::1`."""
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    return _leaf(ca, "localhost", ExtendedKeyUsageOID.SERVER_AUTH, days, x509.SubjectAlternativeName(names))


def issue_client(ca: Issued, common_name: str, *, days: int) -> Issued:
    """Issues a client leaf; its CN is what `DIAGNOS_API_ALLOWED_CLIENT_CN` matches."""
    return _leaf(ca, common_name, ExtendedKeyUsageOID.CLIENT_AUTH, days, None)


def certificate_pem(certificate: x509.Certificate) -> bytes:
    """Returns the PEM encoding of a certificate."""
    return certificate.public_bytes(serialization.Encoding.PEM)


def key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Returns the unencrypted PKCS#8 PEM of a key, which uvicorn reads without a passphrase prompt."""
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
    """Issues a fresh key and a certificate for it that the CA signs."""
    ca_key, ca_certificate = ca
    key = ec.generate_private_key(ec.SECP256R1())
    builder = (
        _builder(_name(common_name), ca_certificate.subject, key, days)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
    )
    if names is not None:
        builder = builder.add_extension(names, critical=False)
    return key, builder.sign(ca_key, hashes.SHA256())


def _builder(
    subject: x509.Name, issuer: x509.Name, key: ec.EllipticCurvePrivateKey, days: int
) -> x509.CertificateBuilder:
    """Returns a builder holding the fields and the key identifier that every certificate here shares."""
    now = datetime.datetime.now(datetime.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )


def _name(common_name: str) -> x509.Name:
    """Returns a subject that carries only a CN."""
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
