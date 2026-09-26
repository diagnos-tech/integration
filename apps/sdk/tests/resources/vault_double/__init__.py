"""🇺🇸 A tiny in-memory vault + R2 double shared by every `resources/` test.

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

🇧🇷 Um duplo minúsculo de cofre + R2 em memória, compartilhado por todo teste de `resources/`.

`FakeVault` de propósito não é um mock dos métodos de `VaultTransport` — é um handler de
`httpx.MockTransport` de verdade, dicts Python puros no lugar do Firestore e do R2, para um bug em como
`resources/` monta uma requisição (um path errado, um campo faltando, um `content-length` que não bate
com o corpo que manda) aparecer como uma falha HTTP de verdade, do mesmo jeito que apareceria contra o
cofre. A metade de documentos segue `routes/factories/versionedDocuments.ts` e
`services/documents/store.ts` regra por regra: paths cientes de fluxo, `security_group_id` no singular,
`encrypted_index` obrigatório, `PUT` assinado travado no tamanho declarado, um slot pendente por fluxo,
reservas só de patch, `expected_latest_version_id` e a cabeça de rascunho. Os `Keyring`s destes testes
são montados à mão com chaves de grupo conhecidas — o ponto inteiro de `resources/` é nunca inventar
chave própria.

Dividido por responsabilidade em módulos irmãos — `_core.py` (o roteador e o relógio/estado
compartilhados), `_documents.py`, `_nodes.py`, `_storage.py` e `_session.py` (a fixture
`Harness`/`harness`) — mas um módulo de teste continua importando este pacote exatamente como sempre
importou o arquivo único `vault_double.py`: só os nomes reexportados abaixo são públicos.

🇺🇸 Named `vault_double`, not `conftest.py`, on purpose: `apps/sdk/tests/conftest.py`
already claims the bare module name every test file imports from
(`from conftest import VECTORS`), and a second file also named `conftest.py`
would collide with it the moment both get imported under the same top-level
name in the same test run.
🇧🇷 Chamado `vault_double`, não `conftest.py`, de propósito:
`apps/sdk/tests/conftest.py` já reivindica o nome de módulo cru que todo arquivo
de teste importa (`from conftest import VECTORS`), e um segundo arquivo também
chamado `conftest.py` colidiria com ele assim que os dois fossem importados
sob o mesmo nome de topo na mesma rodada de teste.
"""

from __future__ import annotations

from ._core import FakeVault
from ._session import Harness, harness, make_documents, make_keyring
from ._wire import ACTOR, VAULT_URL, WORKSPACE_ID

__all__ = ["ACTOR", "VAULT_URL", "WORKSPACE_ID", "FakeVault", "Harness", "harness", "make_documents", "make_keyring"]
