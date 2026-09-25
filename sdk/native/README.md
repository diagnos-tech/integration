# `diagnos._secure` — the memory enclave · o enclave de memória

🇺🇸 A small Rust crate, built into the `diagnos` wheel by maturin, that holds
every secret the SDK ever has — session keys, group DEKs, document keys, the
SDK's own X25519 + ML-KEM-768 identity, the entropy pool — and performs every
operation that needs one. Python only ever holds a handle, `SecretBox`. The
same guarantees reach `diagnos-cli` and `diagnos-api` for free: they never
touch a key, they call the SDK.

🇧🇷 Um crate Rust pequeno, embarcado no wheel `diagnos` pelo maturin, que
guarda todo segredo que o SDK algum dia tem — chaves de sessão, DEKs de grupo,
chaves de documento, a própria identidade X25519 + ML-KEM-768 do SDK, o pool
de entropia — e executa toda operação que precisa de um. O Python só segura
um handle, `SecretBox`. As mesmas garantias chegam a `diagnos-cli` e
`diagnos-api` de graça: eles nunca tocam uma chave, chamam o SDK.

## Why Rust, why here · Por que Rust, por que aqui

🇺🇸 CPython cannot promise where a secret lives. `bytes` are immutable and
may be interned or copied by any slice; a `bytearray` that grows leaves its
old buffer behind for the collector; every object sits in a heap page the
kernel may swap to disk or write into a core dump; and a `fork()` duplicates
all of it into a child nobody audited. A `SecretBox` is a page the crate
controls: it is `mmap`ed anonymously, `mlock`ed so it never reaches swap,
excluded from core dumps, zeroed in a `fork()` child, fenced by guard pages
that turn an out-of-bounds read from any neighbouring code into a fault, and
zeroed with a compiler-proof volatile write the moment the box is dropped.
None of that is expressible from Python.

🇧🇷 O CPython não consegue prometer onde um segredo mora. `bytes` são
imutáveis e podem ser internados ou copiados por qualquer fatia; um
`bytearray` que cresce deixa o buffer antigo para o coletor; todo objeto fica
numa página de heap que o kernel pode mandar ao swap ou escrever num core
dump; e um `fork()` duplica tudo isso num filho que ninguém auditou. Um
`SecretBox` é uma página que o crate controla: é `mmap`ada anônima, `mlock`ada
para nunca chegar ao swap, excluída de core dumps, zerada num filho de
`fork()`, cercada por guard pages que transformam uma leitura fora dos limites
vinda de qualquer código vizinho numa falha, e zerada com uma escrita volátil
à prova de compilador no instante em que a caixa é descartada. Nada disso é
expressável a partir do Python.

## What is guaranteed · O que é garantido

| Threat · Ameaça | Mechanism · Mecanismo | Where · Onde |
|---|---|---|
| Swap / hibernation file · swap / arquivo de hibernação | `mlock` on the data pages (`VirtualLock` on Windows) | `locked/unix.rs`, `locked/windows.rs` |
| Core dump of the process · core dump do processo | `MADV_DONTDUMP` per page + `RLIMIT_CORE = 0` for the process | `locked/unix.rs`, `process.rs` |
| `ptrace` / debugger attach by a same-uid process · attach de `ptrace`/debugger por processo do mesmo uid | `PR_SET_DUMPABLE = 0` (Linux), `PT_DENY_ATTACH` (macOS) | `process.rs` |
| Secrets inherited by a `fork()` child · segredos herdados por um filho de `fork()` | `MADV_WIPEONFORK` + a sentinel word: the child reads zeros and every use raises | `locked/unix.rs`, `locked/mod.rs` |
| Overflow from a neighbouring allocation · overflow de uma alocação vizinha | `PROT_NONE` guard page before and after the data | `locked/unix.rs` |
| Key material surviving in freed memory · material de chave sobrevivendo em memória liberada | `zeroize` (volatile) on drop, on `wipe()`, and on every transient Rust copy (`Zeroizing`) | everywhere · em todo lugar |
| Accidental disclosure from Python · vazamento acidental a partir do Python | no `bytes()`, no buffer protocol, no indexing, redacted `repr`, unhashable, `pickle`/`copy` refused, constant-time `==` | `secret_box.rs` |
| Cloned VM / container RNG · RNG de VM/container clonado | the vault's per-response seed, opened *inside* the enclave and mixed into every DEK and nonce | `entropy.rs`, `secret_box.rs` |

🇺🇸 The last row deserves a sentence: nothing the vault sends as a secret is
ever parsed in Python. The sealed session JSON and the `X-Session-Seed` JSON
are decrypted, parsed and base64-decoded in Rust, straight into locked boxes.

🇧🇷 A última linha merece uma frase: nada que o cofre envia como segredo é
lido em Python. O JSON da sessão selada e o JSON do `X-Session-Seed` são
decifrados, lidos e decodificados de base64 em Rust, direto em caixas travadas.

## What is not · O que não é

- 🇺🇸 **Root, or any process with `CAP_SYS_PTRACE`.** Kernel-level access reads
  any page. The enclave narrows the attack surface to that; it does not
  pretend to be a hardware enclave.
  🇧🇷 **Root, ou qualquer processo com `CAP_SYS_PTRACE`.** Acesso em nível de
  kernel lê qualquer página. O enclave estreita a superfície de ataque a
  isso; não finge ser um enclave de hardware.
- 🇺🇸 **Code running inside the same process.** A malicious dependency shares
  the address space; Rust cannot hide a page from it. What it gains is that
  the secret is never a Python object it can find by walking the heap.
  🇧🇷 **Código rodando dentro do mesmo processo.** Uma dependência maliciosa
  compartilha o espaço de endereços; Rust não consegue esconder uma página
  dela. O que se ganha é que o segredo nunca é um objeto Python que ela
  encontre percorrendo o heap.
- 🇺🇸 **The OpenBao export window.** `session/unseal.py` must serialize the
  keys to JSON to save them: `SecretBox.reveal()` exists only for that, the
  `bytearray`s are zeroed immediately, and the immutable base64 text lives
  until the collector frees it. Milliseconds, opt-in, documented.
  🇧🇷 **A janela de exportação do OpenBao.** `session/unseal.py` precisa
  serializar as chaves em JSON para salvá-las: `SecretBox.reveal()` existe
  só para isso, os `bytearray`s são zerados imediatamente, e o texto base64
  imutável vive até o coletor liberá-lo. Milissegundos, opt-in, documentado.
- 🇺🇸 **Plaintext content and `DIAGNOS_API_TOKEN`.** Decrypted records and
  file bytes are the product and go back to the caller; the token is a
  bearer credential already present in the environment.
  🇧🇷 **Conteúdo em claro e `DIAGNOS_API_TOKEN`.** Registros e bytes de
  arquivo decifrados são o produto e voltam a quem chama; o token é uma
  credencial bearer já presente no ambiente.
- 🇺🇸 **Windows.** `VirtualLock` + zero-on-drop only: no guard pages, no
  fork semantics, no dump advisory. `memory_status()` reports it honestly.
  🇧🇷 **Windows.** Só `VirtualLock` + zero-ao-descartar: sem guard pages,
  sem semântica de fork, sem aviso de dump. `memory_status()` reporta com
  honestidade.

## Operating it · Operando

🇺🇸 Locking pages costs against `RLIMIT_MEMLOCK` (often 64 KiB in a
container). Each box takes one data page plus two guard pages; a session
with a few dozen groups fits in a few hundred KiB. When the kernel refuses,
the crate keeps every other protection and counts the refusal;
`warn_if_unlocked()` emits one `MemoryLockWarning` after unlock. Choose the
policy with `DIAGNOS_MEMORY_LOCK`:

🇧🇷 Travar páginas conta contra o `RLIMIT_MEMLOCK` (muitas vezes 64 KiB num
container). Cada caixa ocupa uma página de dados mais duas guard pages; uma
sessão com algumas dezenas de grupos cabe em algumas centenas de KiB. Quando o
kernel recusa, o crate mantém toda outra proteção e conta a recusa;
`warn_if_unlocked()` emite um `MemoryLockWarning` depois do unlock. Escolha a
política com `DIAGNOS_MEMORY_LOCK`:

| `DIAGNOS_MEMORY_LOCK` | 🇺🇸 Behaviour · 🇧🇷 Comportamento |
|---|---|
| `best-effort` (default · padrão) | keep running, warn once · continua, avisa uma vez |
| `require` | `SecureError` on the first page that will not lock — the process refuses to hold keys in swappable memory · `SecureError` na primeira página que não travar — o processo se recusa a segurar chaves em memória que pode ir ao swap |

🇺🇸 To make locking succeed as a non-root user: raise `ulimit -l`, or grant
`CAP_IPC_LOCK` (`docker run --cap-add IPC_LOCK`, Kubernetes
`capabilities.add: [IPC_LOCK]`) *and* give the interpreter the file
capability `cap_ipc_lock=+p` (`api/Dockerfile` does). `+p`, not `+ep`: a
binary with the effective bit set is refused by the kernel (`EPERM` at
`exec`) whenever the container was not granted the capability, so one
forgotten `cap_add` would become a crash-loop. With `+p` the process always
starts and the enclave raises the capability into the effective set itself,
per thread, right before each `mlock` (`locked/caps.rs`); without the grant
it degrades to best-effort. `memory_status()` reports `ipc_lock_permitted`
and `ipc_lock_effective`. `DIAGNOS_HARDEN_PROCESS=0` skips the process-wide
hardening (only useful to attach a debugger).

🇧🇷 Para o travamento dar certo como usuário sem root: aumente `ulimit -l`,
ou conceda `CAP_IPC_LOCK` (`docker run --cap-add IPC_LOCK`, Kubernetes
`capabilities.add: [IPC_LOCK]`) *e* dê ao interpretador a capability de
arquivo `cap_ipc_lock=+p` (`api/Dockerfile` faz). `+p`, não `+ep`: um
binário com o bit effective é recusado pelo kernel (`EPERM` no `exec`)
sempre que o container não recebeu a capability, então um `cap_add`
esquecido viraria crash-loop. Com `+p` o processo sempre sobe e o enclave
sobe a capability para o conjunto effective sozinho, por thread, logo antes
de cada `mlock` (`locked/caps.rs`); sem a concessão, degrada para
best-effort. `memory_status()` reporta `ipc_lock_permitted` e
`ipc_lock_effective`. `DIAGNOS_HARDEN_PROCESS=0` pula o hardening do
processo inteiro (útil só para anexar um debugger).

## Layout · Estrutura

```
native/
├── Cargo.toml          pinned RustCrypto/dalek stack, release profile with overflow checks
├── src/
│   ├── lib.rs          #![deny(unsafe_code)] crate root; the pymodule
│   ├── locked/         LockedBuffer: mmap + guard pages + mlock + wipe-on-fork; caps.rs raises CAP_IPC_LOCK per thread
│   ├── secret_box.rs   SecretBox: the Python handle and every operation that uses a key
│   ├── buffer.rs       Python buffers in, zeroizing Rust memory out; writable sources are zeroed
│   ├── kdf.rs          HMAC-SHA512, HKDF-SHA256
│   ├── aead.rs         AES-256-GCM
│   ├── hybrid.rs       X25519 + ML-KEM-768 seal/open, HybridKeyPair, sealed-session parsing
│   ├── secretstream.rs libsodium crypto_secretstream_xchacha20poly1305, bit-exact, over a locked 44-byte state
│   ├── stream.rs       SecretStreamPush / SecretStreamPull (GIL released per chunk)
│   ├── entropy.rs      EntropyPool: SHA-256(os_random ‖ seed ‖ counter), state in a locked page
│   ├── process.rs      harden_process(), memory_status() (rlimit/prctl syscalls)
│   ├── rng.rs          the OS CSPRNG as rand_core traits; the crate's only randomness
│   └── error.rs        one Error enum → SecureError (a subclass of diagnos.errors.CryptoError)
└── tests/vectors.rs    the normative vectors in ../tests/vectors, run against the Rust core directly
```

🇺🇸 Every primitive is the RustCrypto or dalek implementation; this crate
contains no cryptographic arithmetic of its own except the secretstream
port, which is a line-by-line translation of libsodium's C, proven against
PyNaCl in the Python suite (`sdk/tests/crypto/test_secure.py`) and against
the TypeScript vectors here. `ExpandedKeyEncoding` for ML-KEM is used on
purpose: the protocol fixes the FIPS 203 expanded key, the form every other
implementation of it emits.

🇧🇷 Toda primitiva é a implementação do RustCrypto ou do dalek; este crate
não contém aritmética criptográfica própria além do porte do secretstream,
que é uma tradução linha a linha do C do libsodium, provada contra o PyNaCl
na suíte Python (`sdk/tests/crypto/test_secure.py`) e contra os vetores em
TypeScript aqui. O `ExpandedKeyEncoding` do ML-KEM é usado de propósito: o
protocolo fixa a chave expandida da FIPS 203, a forma que toda outra
implementação dele emite.

## Build and test · Build e teste

```sh
# 🇺🇸 from apps/integration — the wheel (and this crate) build through uv/maturin
# 🇧🇷 de apps/integration — o wheel (e este crate) constroem via uv/maturin
uv sync --all-packages
make rust-lint    # cargo fmt --check + cargo clippy -D warnings (pedantic)
make rust-test    # unit tests + tests/vectors.rs; PYO3_PYTHON is set by the Makefile
```

🇺🇸 `PYO3_PYTHON` must point at a CPython ≥ 3.11 for `cargo test`; the wheel
is `abi3-py311`, one build per platform. The `.so` is not rebuilt by `uv
sync` after a Rust edit — run `uv sync --reinstall-package diagnos`.

🇧🇷 `PYO3_PYTHON` precisa apontar para um CPython ≥ 3.11 para o `cargo test`;
o wheel é `abi3-py311`, um build por plataforma. O `.so` não é reconstruído
pelo `uv sync` depois de editar Rust — rode `uv sync --reinstall-package diagnos`.
