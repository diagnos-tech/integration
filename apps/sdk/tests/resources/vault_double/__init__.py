"""A tiny in-memory vault + R2 double shared by every `resources/` test.

`FakeVault` is deliberately not a mock of `VaultTransport`'s methods — it is a real
`httpx.MockTransport` handler, plain Python dicts standing in for Firestore and R2, so a bug in how
`resources/` builds a request (a wrong path, a missing field, a `content-length` that does not match
the body it sends) shows up as a real HTTP-shaped failure, the same way it would against the vault. The
document half follows `routes/factories/versionedDocuments.ts` and `services/documents/store.ts` rule
for rule: stream-aware paths, the singular `security_group_id`, required `encrypted_index`, a signed
`PUT` locked to the declared size, one pending slot per stream, patch-only reservations,
`expected_latest_version_id`, and the draft head. `Keyring`s in these tests are built by hand with
known group keys — the whole point of `resources/` is that it never invents keys of its own.

Split by responsibility across sibling modules — `_core.py` (the router and shared clock/state),
`_documents.py`, `_nodes.py`, `_storage.py` and `_session.py` (the `Harness`/`harness` fixture) — but a
test module keeps importing this package exactly as it always imported the single `vault_double.py`
file: only the names re-exported below are public.
"""

from __future__ import annotations

from ._core import FakeVault
from ._session import Harness, harness, make_documents, make_keyring
from ._wire import ACTOR, VAULT_URL, WORKSPACE_ID

__all__ = ["ACTOR", "VAULT_URL", "WORKSPACE_ID", "FakeVault", "Harness", "harness", "make_documents", "make_keyring"]
