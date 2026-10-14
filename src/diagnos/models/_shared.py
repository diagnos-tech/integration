"""Validation plumbing every sealed record shares: the vault-vs-caller context and the typo/lossless rule.

Nothing here is domain-specific. `_patients.py` and `_exams.py` (and any
future record type) build on `_Record` and `vault_context()` rather than each
re-implementing "was this plaintext the vault handed back, or something a
caller just typed".
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from typing import Any, ClassVar, Final

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

# Validation-context key that marks "this came from the vault, not from the caller" (see `_Record`).
_FROM_VAULT: Final[str] = "diagnos.from_vault"


def vault_context() -> dict[str, bool]:
    """Return the pydantic validation context the SDK uses for plaintext it just decrypted.

    Records built by the caller are strict (an unknown field is a typo and
    fails before anything is encrypted); records decrypted from the vault are
    tolerant (a field the web app added later is kept, so a read-modify-write
    round trip never drops it). This context is what tells the two apart.

    Returns:
        A context to pass as `context=` to `model_validate`.
    """
    return {_FROM_VAULT: True}


def _from_vault(info: ValidationInfo) -> bool:
    """Return `True` when validating plaintext the SDK decrypted."""
    return bool(info.context and info.context.get(_FROM_VAULT))


# How close an unknown key must be to a real field to count as a typo (`difflib` ratio).
TYPO_CUTOFF: Final[float] = 0.8


class _Record(BaseModel):
    """Base of every sealed record: typo-proof for the caller, lossless for fields the SDK does not model.

    The vault never sees plaintext, so nothing downstream validates a
    record: this model is the last check before encryption. Two failure
    modes pull in opposite directions, and the rule below handles both:

    - A **typo** (`birthdate` for `birth_date`) would store the value under
      a key nobody reads. Any unknown key that closely resembles a real
      field is refused, naming the field it resembles.
    - A **field the web app added** before this SDK modelled it must survive
      a read-modify-write (`get()`, change one thing, `update()`), or the
      SDK would silently delete clinical data. Any other unknown key is kept
      verbatim (`extra="allow"`), in the order it came.

    Plaintext decrypted from the vault skips the typo check entirely: it is
    what the web app wrote, not something the caller typed.
    """

    # `hide_input_in_errors`: a validation error names the field, never echoes the clinical value (logs).
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)

    # Keys that belong somewhere else (a method argument, clear `meta`), with where they go.
    _MISPLACED: ClassVar[dict[str, str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _reject_typos(cls, data: Any, info: ValidationInfo) -> Any:
        """Refuse unknown keys that look like a misspelled field (or belong elsewhere), naming the fix."""
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
        raise ValueError(f"{cls.__name__}: unknown field that looks like a typo, did you mean: {hints}")
