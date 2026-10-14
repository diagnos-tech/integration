"""Mixes the vault's per-response seed into local randomness (PROTOCOL §4); the state lives in the enclave.

Threat model: a VM cloned or restored from a snapshot (a container image, a
forked sandbox, a resumed suspend-to-disk) can boot with an OS RNG that
hasn't re-seeded from fresh hardware entropy yet, so two clones can draw the
same "random" bytes from `os.urandom` in their first moments. The vault's
`random_seed` (itself derived from the vault's own entropy, unique per
response) gives every SDK instance something a sibling clone does not share.
Mixing it in can only add entropy, never remove it — `os.urandom` output
always dominates each block, so a seed of all zeros degrades gracefully to
plain OS randomness rather than to something weaker.
"""

from __future__ import annotations

from diagnos import _secure

from .secure import SecretBox, SecretLike


class EntropyMixer:
    """Stateful mixer that holds the latest server seed (hashed, in a locked page), never the OS RNG state.

    It augments the OS RNG and never substitutes for it: every 32-byte
    block is `SHA-256(os_random(32) ‖ state ‖ counter)`, so a caller that
    never invokes `mix()` gets output indistinguishable from
    `secrets.token_bytes`. `random_secret()` writes straight into a locked
    box, so a DEK born here never exists on the Python heap.
    """

    __slots__ = ("_pool",)

    def __init__(self) -> None:
        """Create an unseeded mixer, equivalent to `secrets.token_bytes` until `mix()` is called."""
        self._pool = _secure.EntropyPool()

    def mix(self, seed: SecretLike) -> None:
        """Replace the mixed-in seed.

        Resets the block counter too: a new seed starts its own sequence and
        does not continue the old one.

        Args:
            seed: A freshly opened `random_seed`, already held in a `SecretBox`.
        """
        self._pool.mix(seed)

    def random(self, n: int) -> bytes:
        """Return `n` random bytes for public values such as nonces, salts and client references.

        Args:
            n: The number of bytes to draw.

        Returns:
            `n` bytes mixing OS randomness with the current seed.

        Raises:
            ValueError: If `n` is negative.
        """
        if n < 0:
            raise ValueError("EntropyMixer.random: n must not be negative")
        return self._pool.random(n)

    def random_secret(self, n: int) -> SecretBox:
        """Return `n` random bytes born inside a locked box, for DEKs and every other key this process creates.

        Args:
            n: The number of bytes to draw.

        Returns:
            A locked `SecretBox` holding the bytes; they never exist on the Python heap.
        """
        return self._pool.random_secret(n)
