"""🇺🇸 Mixes the vault's per-response seed into local randomness (PROTOCOL §4), state kept in the enclave.

Threat model: a VM cloned or restored from a snapshot (a container image, a
forked sandbox, a resumed suspend-to-disk) can boot with an OS RNG that
hasn't re-seeded from fresh hardware entropy yet, so two clones can draw the
same "random" bytes from `os.urandom` in their first moments. The vault's
`random_seed` (itself derived from the vault's own entropy, unique per
response) gives every SDK instance something a sibling clone does not share.
Mixing it in can only add entropy, never remove it — `os.urandom` output
always dominates each block, so a seed of all zeros degrades gracefully to
plain OS randomness rather than to something weaker.

🇧🇷 Mistura a semente por-resposta do cofre à aleatoriedade local (PROTOCOL §4), estado guardado no enclave.

Modelo de ameaça: uma VM clonada ou restaurada de um snapshot (uma imagem de
container, um sandbox bifurcado, um suspend-to-disk retomado) pode subir com
um RNG do SO que ainda não se re-semeou com entropia de hardware fresca,
então dois clones podem sortear os mesmos bytes "aleatórios" de
`os.urandom` nos primeiros instantes. O `random_seed` do cofre (ele
próprio derivado da entropia do cofre, único por resposta) dá a cada
instância de SDK algo que um clone irmão não compartilha. Misturá-lo só pode
somar entropia, nunca remover — a saída de `os.urandom` sempre domina cada
bloco, então uma semente de puros zeros degrada graciosamente para
aleatoriedade pura do SO, não para algo mais fraco.
"""

from __future__ import annotations

from diagnos import _secure

from .secure import SecretBox, SecretLike


class EntropyMixer:
    """🇺🇸 Stateful mixer: holds the latest server seed (hashed, in a locked page), never the OS RNG state.

    It augments the OS RNG; it never substitutes for it — every 32-byte
    block is `SHA-256(os_random(32) ‖ state ‖ counter)`, so a caller that
    never invokes `mix()` gets output indistinguishable from
    `secrets.token_bytes`. `random_secret()` writes straight into a locked
    box: a DEK born here never exists on the Python heap.

    🇧🇷 Misturador com estado: guarda a última semente do servidor (em hash, numa página travada), nunca o RNG do SO.

    Ele aumenta o RNG do SO; nunca o substitui — todo bloco de 32 bytes é
    `SHA-256(os_random(32) ‖ estado ‖ contador)`, então quem nunca chama
    `mix()` recebe uma saída indistinguível de `secrets.token_bytes`.
    `random_secret()` escreve direto numa caixa travada: uma DEK nascida
    aqui nunca existe no heap do Python.
    """

    __slots__ = ("_pool",)

    def __init__(self) -> None:
        """🇺🇸 Starts unseeded — equivalent to `secrets.token_bytes` until `mix()` is called.

        🇧🇷 Começa sem semente — equivalente a `secrets.token_bytes` até `mix()` ser chamado.
        """
        self._pool = _secure.EntropyPool()

    def mix(self, seed: SecretLike) -> None:
        """🇺🇸 Replaces the mixed-in seed (a freshly-opened `random_seed`, already a `SecretBox`).

        Resets the block counter too: a new seed starts its own sequence, it
        doesn't continue the old one.

        🇧🇷 Substitui a semente misturada (um `random_seed` recém-aberto, já um `SecretBox`).

        Também reinicia o contador de blocos: uma semente nova começa a
        própria sequência, não continua a antiga.
        """
        self._pool.mix(seed)

    def random(self, n: int) -> bytes:
        """🇺🇸 `n` bytes for public values — nonces, salts, client references.

        🇧🇷 `n` bytes para valores públicos — nonces, salts, referências de cliente.
        """
        if n < 0:
            raise ValueError("EntropyMixer.random: n não pode ser negativo")
        return self._pool.random(n)

    def random_secret(self, n: int) -> SecretBox:
        """🇺🇸 `n` bytes born inside a locked box — for DEKs and every other key this process creates.

        🇧🇷 `n` bytes nascidos dentro de uma caixa travada — para DEKs e toda outra chave que este processo cria.
        """
        return self._pool.random_secret(n)
