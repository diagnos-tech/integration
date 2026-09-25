# Conventions · Convenções

🇺🇸 This folder is published as open source and read by people who never saw
the rest of the monorepo. Every file has to explain itself, in both languages.
🇧🇷 Esta pasta é publicada como código aberto e lida por gente que nunca viu o
resto do monorepo. Todo arquivo tem que se explicar sozinho, nas duas línguas.

## Comments · Comentários

🇺🇸 Every module, class and public function has a docstring with an English
paragraph prefixed `🇺🇸` followed by the Portuguese one prefixed `🇧🇷`. Inline
comments follow the same pair on consecutive lines. Comments explain the
**why** (the threat, the cost, the protocol constraint), never restate the
code, and never mention how the file came to exist.
🇧🇷 Todo módulo, classe e função pública tem docstring com um parágrafo em
inglês prefixado `🇺🇸` seguido do português prefixado `🇧🇷`. Comentário em
linha segue o mesmo par em linhas consecutivas. Comentário explica o
**porquê** (a ameaça, o custo, a restrição do protocolo), nunca repete o
código, e nunca fala de como o arquivo surgiu.

```python
def sign(request: CanonicalRequest, sign_key: bytes) -> str:
    """🇺🇸 HMAC-SHA512 over the canonical string, hex-encoded.

    The vault reconstructs the same string from the raw request; any byte we
    normalize differently is a 401, so this mirrors `canonical.ts` verbatim.

    🇧🇷 HMAC-SHA512 sobre a string canônica, em hex.

    O cofre reconstrói a mesma string a partir da requisição crua; qualquer
    byte normalizado diferente é 401, então isto espelha `canonical.ts` ao pé
    da letra.
    """
```

🇺🇸 `scripts/check_bilingual.py` (part of `make lint`) fails the build when a
module, class or public function lacks either flag.
🇧🇷 `scripts/check_bilingual.py` (parte de `make lint`) derruba o build quando
um módulo, classe ou função pública está sem uma das bandeiras.

## Structure · Estrutura

- 🇺🇸 Small files, one responsibility. A folder per domain (`crypto/`,
  `session/`, `resources/`, `transport/`). No file above ~250 lines.
  🇧🇷 Arquivos pequenos, uma responsabilidade. Uma pasta por domínio. Nenhum
  arquivo acima de ~250 linhas.
- 🇺🇸 Public API lives in `diagnos/__init__.py` and is stable; everything
  under `_internal`-style names is not.
  🇧🇷 A API pública vive em `diagnos/__init__.py` e é estável; o resto não é.
- 🇺🇸 `cli` and `api` import **only** `diagnos`. If they need something the
  SDK does not expose, the SDK grows — the shells never reimplement.
  🇧🇷 `cli` e `api` importam **só** `diagnos`. Se precisam de algo que o SDK
  não expõe, o SDK cresce — as cascas nunca reimplementam.
- 🇺🇸 Pending decisions are `TODO(gustavo): ...`. No FIXME, no HACK.
  🇧🇷 Decisão pendente é `TODO(gustavo): ...`. Sem FIXME, sem HACK.

## Security · Segurança

- 🇺🇸 Secrets (session keys, DEKs, private keys) never live in a Python
  `bytearray`. They live in `diagnos._secure.SecretBox` — page-locked Rust
  memory (`sdk/native`), zeroed on drop, never exposed as `bytes`. The only
  exit is `reveal()`, reserved for the OpenBao auto-unseal export; every
  other operation (HMAC, HKDF, AEAD, the hybrid handshake) runs inside the
  box and returns only what the caller asked for.
  🇧🇷 Segredos (chaves de sessão, DEKs, chaves privadas) nunca vivem num
  `bytearray` Python. Vivem em `diagnos._secure.SecretBox` — memória Rust
  travada em página (`sdk/native`), zerada ao descartar, nunca exposta como
  `bytes`. A única saída é `reveal()`, reservada para a exportação do
  auto-unseal no OpenBao; toda outra operação (HMAC, HKDF, AEAD, o
  handshake híbrido) roda dentro da caixa e devolve só o que foi pedido.
- 🇺🇸 Rust files follow the same bilingual rule as Python: every `//!` module
  doc and `///` item doc carries both `🇺🇸` and `🇧🇷`, enforced by
  `scripts/check_bilingual.py` over `native/src` and `native/tests`.
  `unsafe` is confined to `native/src/locked/` (memory and capabilities), `native/src/buffer.rs` and `native/src/process.rs` (rlimit/prctl) —
  the two places that actually touch raw memory (`mlock`, guard pages, the
  FFI buffer handed to pyo3) — and every `unsafe` block carries a `SAFETY:`
  comment stating the invariant that makes it sound.
  🇧🇷 Arquivo Rust segue a mesma regra bilíngue do Python: toda doc `//!` de
  módulo e `///` de item carrega `🇺🇸` e `🇧🇷`, garantido pelo
  `scripts/check_bilingual.py` sobre `native/src` e `native/tests`.
  `unsafe` fica confinado a `native/src/locked/` (memória e capabilities), `native/src/buffer.rs` e `native/src/process.rs` (rlimit/prctl) —
  os dois lugares que de fato tocam memória crua (`mlock`, guard pages, o
  buffer FFI entregue ao pyo3) — e todo bloco `unsafe` carrega um comentário
  `SAFETY:` dizendo o invariante que o torna correto.
- 🇺🇸 Every byte format is normative in `docs/PROTOCOL.md` and pinned by the
  vectors in `sdk/tests/vectors/`, generated from the TypeScript reference.
  🇧🇷 Todo formato de bytes é normativo em `docs/PROTOCOL.md` e travado pelos
  vetores em `sdk/tests/vectors/`, gerados da referência em TypeScript.

## Tooling · Ferramentas

```sh
uv sync --all-packages          # 🇺🇸 one venv for the workspace · 🇧🇷 um venv para o workspace
uv run --package diagnos pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy sdk/src cli/src api/src
```
