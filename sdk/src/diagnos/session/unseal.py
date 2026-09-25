"""🇺🇸 Optional auto-unseal through OpenBao: restart without a human by restoring the unlocked state.

`docs/PROTOCOL.md §11`: enrollment is a human clicking "approve" on a web
page, which is exactly the step a long-running or auto-restarting process
(a worker, a cron job) cannot repeat on every boot. Saving the unlocked
state to OpenBao trades that human step for a different, deliberate one:
the group DEKs — normally alive only in this process's locked memory — now
also sit in OpenBao's encrypted KV storage, so whoever can read
`OPENBAO_ADDR`'s `<prefix>/<workspace_id>/<account_id>` path can read the
workspace exactly as this SDK process can. Scoping the OpenBao token to
that one path is what keeps this an intentional trade rather than a silent
widening of who can decrypt.

This is also the one place secrets leave the enclave as clear text: to be
written into a JSON body, each `SecretBox` is `reveal()`ed into a
`bytearray` that is zeroed as soon as the request is built. The base64 text
inside that JSON, and the `bytes` `base64` produces on restore, are
immutable Python objects that live until the collector frees them — an
exposure window measured in milliseconds, accepted knowingly, and the
reason this path is opt-in.

🇧🇷 Auto-unseal opcional via OpenBao: reiniciar sem humano restaurando o
estado desbloqueado.

`docs/PROTOCOL.md §11`: enrollment é uma pessoa clicando "aprovar" numa
página web, exatamente o passo que um processo de longa duração ou que
reinicia sozinho (um worker, um cron) não consegue repetir a cada subida.
Salvar o estado desbloqueado no OpenBao troca esse passo humano por outro,
deliberado: as DEKs de grupo — normalmente vivas só na memória travada deste
processo — agora também moram no armazenamento KV cifrado do OpenBao, então
quem conseguir ler o path `<prefix>/<workspace_id>/<account_id>` de
`OPENBAO_ADDR` lê o workspace exatamente como este processo do SDK lê.
Restringir o token do OpenBao a esse único path é o que mantém isto uma
troca intencional em vez de um alargamento silencioso de quem consegue
decifrar.

Este também é o único lugar em que segredos saem do enclave em claro: para
serem escritos num corpo JSON, cada `SecretBox` é `reveal()`ado num
`bytearray` que é zerado assim que a requisição é montada. O texto base64
dentro desse JSON, e os `bytes` que o `base64` produz no restore, são
objetos Python imutáveis que vivem até o coletor liberá-los — uma janela de
exposição medida em milissegundos, aceita conscientemente, e o motivo de
este caminho ser opt-in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox, secret_from_b64url, zero
from diagnos.errors import ConfigError
from diagnos.session.keyring import Keyring, SessionKeys

# 🇺🇸 Same reasoning as `enrollment.py`: `diagnos.transport` eagerly imports
# `diagnos.session.keyring`, so a module-level import of any of its
# submodules here would close an import cycle. `Settings` is only ever used
# as a type hint — its fields are read through plain attribute access.
# 🇧🇷 Mesmo raciocínio de `enrollment.py`: `diagnos.transport` importa
# `diagnos.session.keyring` de forma antecipada, então um import no nível do
# módulo de qualquer submódulo dele aqui fecharia um ciclo. `Settings` só é
# usado como type hint — seus campos são lidos por acesso a atributo simples.
if TYPE_CHECKING:
    from diagnos.transport.config import Settings

# 🇺🇸 `docs/PROTOCOL.md §11`'s `"v": 1` — bumped only if the saved shape ever
# changes incompatibly; a mismatch means "not this SDK version's format",
# treated the same as "nothing saved" rather than a crash.
# 🇧🇷 O `"v": 1` de `docs/PROTOCOL.md §11` — só sobe se a forma salva mudar
# de jeito incompatível; um valor diferente significa "não é o formato desta
# versão do SDK", tratado igual a "nada salvo" em vez de uma quebra.
_STATE_VERSION = 1

# 🇺🇸 Mirrors `SessionKeys.is_valid`'s own margin (`session/keyring.py`): a
# restore that leaves less than a minute before `session_expires_at` is not
# worth handing back — the caller would immediately have to re-enroll
# anyway, so `restore` reports "nothing usable" up front.
# 🇧🇷 Espelha a margem de `SessionKeys.is_valid` (`session/keyring.py`): um
# restore que deixaria menos de um minuto até `session_expires_at` não vale
# a pena devolver — quem chama teria que refazer o enrollment na hora mesmo,
# então `restore` já reporta "nada aproveitável".
_MIN_REMAINING_VALIDITY_SECONDS = 60


@dataclass(frozen=True)
class UnsealedState:
    """🇺🇸 Everything needed to resume: the key pair and the keyring.

    🇧🇷 Tudo para retomar: o par de chaves e o keyring.
    """

    keypair: HybridKeyPair
    keyring: Keyring


class _Exporter:
    """🇺🇸 Reveals boxes for one `save()` and zeroes every revealed buffer afterwards, success or not.

    🇧🇷 Revela caixas para um `save()` e zera todo buffer revelado depois, com sucesso ou não.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts with nothing revealed. 🇧🇷 Começa sem nada revelado."""
        self._revealed: list[bytearray] = []

    def b64url(self, box: SecretBox) -> str:
        """🇺🇸 `reveal()` then encode; the buffer is remembered for `close()`.

        🇧🇷 `reveal()` e depois codifica; o buffer fica lembrado para `close()`.
        """
        buffer = box.reveal()
        self._revealed.append(buffer)
        return b64url_encode(buffer)

    def close(self) -> None:
        """🇺🇸 Zero every revealed buffer. 🇧🇷 Zera todo buffer revelado."""
        for buffer in self._revealed:
            zero(buffer)
        self._revealed.clear()


class OpenBaoStore:
    """🇺🇸 KV v2 store at `<prefix>/<workspace_id>/<account_id>` (PROTOCOL §11).

    🇧🇷 Store KV v2 em `<prefix>/<workspace_id>/<account_id>` (PROTOCOL §11).
    """

    def __init__(self, settings: Settings, *, workspace_id: str, account_id: str, client: Any | None = None) -> None:
        """🇺🇸 `hvac` is optional (`pip install "diagnos[openbao]"`); import it here, not at module scope.

        Importing lazily means the SDK's core import path never requires
        `hvac` to be installed — only a process that actually configures
        `OPENBAO_ADDR`/`OPENBAO_TOKEN` and constructs this class pays that
        cost, and pays for it with a clear message instead of a bare
        `ModuleNotFoundError` several frames deep.

        🇧🇷 `hvac` é opcional (`pip install "diagnos[openbao]"`); importe
        aqui, não no nível do módulo.

        Importar de forma tardia significa que o caminho de import principal
        do SDK nunca exige `hvac` instalado — só um processo que de fato
        configura `OPENBAO_ADDR`/`OPENBAO_TOKEN` e constrói esta classe paga
        esse custo, e paga com uma mensagem clara em vez de um
        `ModuleNotFoundError` cru vários quadros abaixo.
        """
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ConfigError(
                "🇺🇸 OpenBao auto-unseal needs the optional 'hvac' dependency; install it with "
                'pip install "diagnos[openbao]". '
                "🇧🇷 O auto-unseal do OpenBao precisa da dependência opcional 'hvac'; instale com "
                'pip install "diagnos[openbao]".'
            ) from exc

        # 🇺🇸 Kept as an instance attribute (not re-imported per call) so
        # `restore()` can catch "no secret at this path" without needing its
        # own module-level `import hvac` — the whole point of the try/except
        # above is that this is the *one* place that import happens.
        # 🇧🇷 Guardado como atributo de instância (sem reimportar a cada
        # chamada) para `restore()` capturar "nenhum segredo neste path" sem
        # precisar de seu próprio `import hvac` no nível do módulo — o
        # ponto inteiro do try/except acima é este ser o *único* lugar que
        # esse import acontece.
        self._invalid_path_exc: type[BaseException] = hvac.exceptions.InvalidPath
        self._client: Any = None
        if client is not None:
            self._client = client
        else:
            self._client = hvac.Client(
                url=settings.openbao_addr,
                token=settings.openbao_token,
                namespace=settings.openbao_namespace,
            )
        self._mount_point = settings.openbao_mount
        self._path = f"{settings.openbao_path_prefix}/{workspace_id}/{account_id}"

    def restore(self, *, now: int | None = None) -> UnsealedState | None:
        """🇺🇸 The saved state if still valid, else `None`.

        Every "not usable" outcome — nothing saved, a version this SDK does
        not recognize, a session too close to `session_expires_at` — returns
        `None` rather than raising, because the caller's response to all of
        them is identical: enroll again.

        🇧🇷 O estado salvo se ainda válido, senão `None`.

        Todo desfecho "não aproveitável" — nada salvo, uma versão que este
        SDK não reconhece, uma sessão perto demais de `session_expires_at`
        — retorna `None` em vez de lançar, porque a resposta de quem chama a
        todos eles é a mesma: fazer o enrollment de novo.
        """
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=self._path,
                mount_point=self._mount_point,
                raise_on_deleted_version=True,
            )
        except self._invalid_path_exc:
            return None

        data = response["data"]["data"]
        if data.get("v") != _STATE_VERSION:
            return None

        current = now if now is not None else int(time.time())
        session_expires_at = int(data["session_expires_at"])
        if session_expires_at - current <= _MIN_REMAINING_VALIDITY_SECONDS:
            return None

        keypair = HybridKeyPair.from_secrets(
            secret_from_b64url(data["x25519_secret"]),
            secret_from_b64url(data["mlkem768_secret"]),
        )
        session = SessionKeys(
            session_id=data["session_id"],
            sign_key=secret_from_b64url(data["sign_key"]),
            enc_key=secret_from_b64url(data["enc_key"]),
            expires_at=session_expires_at,
        )
        group_keys = {
            security_group_id: secret_from_b64url(wrapped)
            for security_group_id, wrapped in data.get("group_keys", {}).items()
        }
        keyring = Keyring(enrollment_id=data["enrollment_id"], session=session, group_keys=group_keys)
        return UnsealedState(keypair=keypair, keyring=keyring)

    def save(self, state: UnsealedState) -> None:
        """🇺🇸 Persist the unlocked state, `docs/PROTOCOL.md §11`'s exact JSON shape.

        🇧🇷 Persiste o estado desbloqueado, na forma de JSON exata de `docs/PROTOCOL.md §11`.
        """
        keypair = state.keypair
        session = state.keyring.session
        exporter = _Exporter()
        try:
            secret = {
                "v": _STATE_VERSION,
                "enrollment_id": state.keyring.enrollment_id,
                "x25519_secret": exporter.b64url(keypair.x25519_secret()),
                "mlkem768_secret": exporter.b64url(keypair.mlkem768_secret()),
                "session_id": session.session_id,
                "sign_key": exporter.b64url(session.sign_key),
                "enc_key": exporter.b64url(session.enc_key),
                "session_expires_at": session.expires_at,
                "group_keys": {
                    security_group_id: exporter.b64url(dek)
                    for security_group_id, dek in state.keyring.group_keys.items()
                },
                "saved_at": int(time.time()),
            }
            self._client.secrets.kv.v2.create_or_update_secret(
                path=self._path,
                secret=secret,
                mount_point=self._mount_point,
            )
        finally:
            exporter.close()

    def clear(self) -> None:
        """🇺🇸 Forget the saved state (session lock).

        🇧🇷 Esquece o estado salvo (lock da sessão).
        """
        self._client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=self._path,
            mount_point=self._mount_point,
        )
