"""🇺🇸 Validation plumbing every sealed record shares: the vault-vs-caller context and the typo/lossless rule.

Nothing here is domain-specific — `_patients.py`/`_exams.py` (and any future
record type) build on `_Record` and `vault_context()` rather than each
re-implementing "was this plaintext the vault handed back, or something a
caller just typed".

🇧🇷 Encanamento de validação que todo registro selado compartilha: o contexto cofre-vs-quem-chama e a
regra de digitação/sem perda.

Nada aqui é específico de domínio — `_patients.py`/`_exams.py` (e qualquer
tipo de registro futuro) constroem sobre `_Record` e `vault_context()` em
vez de cada um reimplementar "este texto claro veio do cofre, ou é algo que
quem chama acabou de digitar".
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from typing import Any, ClassVar, Final

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

# 🇺🇸 Validation-context key that marks "this came from the vault, not from the caller" (see `_Record`).
# 🇧🇷 Chave do contexto de validação que marca "isto veio do cofre, não de quem chama" (ver `_Record`).
_FROM_VAULT: Final[str] = "diagnos.from_vault"


def vault_context() -> dict[str, bool]:
    """🇺🇸 The pydantic validation context the SDK uses for plaintext it just decrypted.

    Records built by the caller are strict (an unknown field is a typo and
    fails before anything is encrypted); records decrypted from the vault are
    tolerant (a field the web app added later is kept, so a read-modify-write
    round trip never drops it). This context is what tells the two apart.

    🇧🇷 O contexto de validação do pydantic que o SDK usa para o texto claro que acabou de decifrar.

    Registros montados por quem chama são estritos (um campo desconhecido é
    erro de digitação e falha antes de qualquer coisa ser cifrada);
    registros decifrados do cofre são tolerantes (um campo que o app web
    acrescentou depois é mantido, então um ciclo ler-modificar-gravar nunca
    o perde). Este contexto é o que separa os dois.
    """
    return {_FROM_VAULT: True}


def _from_vault(info: ValidationInfo) -> bool:
    """🇺🇸 `True` when validating plaintext the SDK decrypted. 🇧🇷 `True` ao validar texto claro que o SDK decifrou."""
    return bool(info.context and info.context.get(_FROM_VAULT))


# 🇺🇸 How close an unknown key must be to a real field to count as a typo (`difflib` ratio).
# 🇧🇷 Quão perto de um campo real uma chave desconhecida precisa estar para contar como erro de digitação.
TYPO_CUTOFF: Final[float] = 0.8


class _Record(BaseModel):
    """🇺🇸 Base of every sealed record: typo-proof for the caller, lossless for fields the SDK does not model.

    The vault never sees plaintext, so nothing downstream validates a
    record: this model is the last check before encryption. Two failure
    modes pull in opposite directions, and the rule below handles both:

    - A **typo** (`birthdate` for `birth_date`) would store the value under
      a key nobody reads. Any unknown key that closely resembles a real
      field is refused, naming the field it resembles.
    - A **field the web app added** before this SDK modelled it must survive
      a read-modify-write — `get()`, change one thing, `update()` — or the
      SDK would silently delete clinical data. Any other unknown key is kept
      verbatim (`extra="allow"`), in the order it came.

    Plaintext decrypted from the vault skips the typo check entirely: it is
    what the web app wrote, not something the caller typed.

    🇧🇷 Base de todo registro selado: à prova de erro de digitação para quem chama, sem perda para
    campos que o SDK não modela.

    O cofre nunca vê texto claro, então nada adiante valida um registro:
    este modelo é a última checagem antes da cifragem. Duas falhas puxam
    em direções opostas, e a regra abaixo cobre as duas:

    - Um **erro de digitação** (`birthdate` por `birth_date`) guardaria o
      valor numa chave que ninguém lê. Toda chave desconhecida muito
      parecida com um campo real é recusada, nomeando o campo parecido.
    - Um **campo que o app web acrescentou** antes de este SDK modelá-lo
      precisa sobreviver a um ler-modificar-gravar — `get()`, mudar uma
      coisa, `update()` — senão o SDK apagaria dado clínico em silêncio.
      Qualquer outra chave desconhecida é mantida como veio (`extra="allow"`).

    Texto claro decifrado do cofre pula a checagem de digitação: é o que o
    app web gravou, não algo que quem chama digitou.
    """

    # 🇺🇸 `hide_input_in_errors`: a validation error names the field, never echoes the clinical value (logs).
    # 🇧🇷 `hide_input_in_errors`: um erro de validação nomeia o campo, nunca ecoa o valor clínico (logs).
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)

    # 🇺🇸 Keys that belong somewhere else (a method argument, clear `meta`), with where they go.
    # 🇧🇷 Chaves que pertencem a outro lugar (um argumento de método, o `meta` em claro), com o destino.
    _MISPLACED: ClassVar[dict[str, str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _reject_typos(cls, data: Any, info: ValidationInfo) -> Any:
        """🇺🇸 Refuses unknown keys that look like a misspelled field (or belong elsewhere), naming the fix.

        🇧🇷 Recusa chaves desconhecidas que parecem um campo digitado errado (ou de outro lugar), nomeando a correção.
        """
        if _from_vault(info) or not isinstance(data, Mapping):
            return data
        misplaced = [f"{key!r}: {cls._MISPLACED[key]}" for key in data if key in cls._MISPLACED]
        if misplaced:
            raise ValueError(f"{cls.__name__}: {'; '.join(misplaced)}")
        known = set(cls.model_fields)
        typos = {}
        for key in data:
            if key in known:
                continue
            close = difflib.get_close_matches(str(key), known, n=1, cutoff=TYPO_CUTOFF)
            if close:
                typos[key] = close[0]
        if not typos:
            return data
        hints = ", ".join(f"{key!r} → {field!r}" for key, field in typos.items())
        raise ValueError(
            f"{cls.__name__}: unknown field that looks like a typo, did you mean: {hints} · campo desconhecido "
            f"com cara de erro de digitação, quis dizer: {hints}"
        )
