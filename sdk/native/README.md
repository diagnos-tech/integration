# `diagnos._secure` — the memory enclave

**English** · [Português (Brasil)](README.pt-BR.md)

A small Rust crate, built into the `diagnos` wheel by maturin, that holds
every secret the SDK ever has — session keys, group DEKs, document keys, the
SDK's own X25519 + ML-KEM-768 identity, the entropy pool — and performs every
operation that needs one. Python only ever holds a handle, `SecretBox`. The
same guarantees reach `diagnos-cli` and `diagnos-api` for free: they never
touch a key, they call the SDK.

## Why Rust, why here

CPython cannot promise where a secret lives. `bytes` are immutable and
may be interned or copied by any slice; a `bytearray` that grows leaves its
old buffer behind for the collector; every object sits in a heap page the
kernel may swap to disk or write into a core dump; and a `fork()` duplicates
all of it into a child nobody audited. A `SecretBox` is a page the crate
controls: it is `mmap`ed anonymously, `mlock`ed so it never reaches swap,
excluded from core dumps, zeroed in a `fork()` child, fenced by guard pages
that turn an out-of-bounds read from any neighbouring code into a fault, and
zeroed with a compiler-proof volatile write the moment the box is dropped.
None of that is expressible from Python.

## What is guaranteed

| Threat | Mechanism | Where |
|---|---|---|
| Swap / hibernation file | `mlock` on the data pages (`VirtualLock` on Windows) | `locked/unix.rs`, `locked/windows.rs` |
| Core dump of the process | `MADV_DONTDUMP` per page + `RLIMIT_CORE = 0` for the process | `locked/unix.rs`, `process.rs` |
| `ptrace` / debugger attach by a same-uid process | `PR_SET_DUMPABLE = 0` (Linux), `PT_DENY_ATTACH` (macOS) | `process.rs` |
| Secrets inherited by a `fork()` child | `MADV_WIPEONFORK` + a sentinel word: the child reads zeros and every use raises | `locked/unix.rs`, `locked/mod.rs` |
| Overflow from a neighbouring allocation | `PROT_NONE` guard page before and after the data | `locked/unix.rs` |
| Key material surviving in freed memory | `zeroize` (volatile) on drop, on `wipe()`, and on every transient Rust copy (`Zeroizing`) | everywhere |
| Accidental disclosure from Python | no `bytes()`, no buffer protocol, no indexing, redacted `repr`, unhashable, `pickle`/`copy` refused, constant-time `==` | `secret_box.rs` |
| Cloned VM / container RNG | the vault's per-response seed, opened *inside* the enclave and mixed into every DEK and nonce | `entropy.rs`, `secret_box.rs` |

The last row deserves a sentence: nothing the vault sends as a secret is
ever parsed in Python. The sealed session JSON and the `random_seed` JSON
(carried in the response envelope, not a header) are decrypted, parsed and
base64-decoded in Rust, straight into locked boxes.

## What is not

- **Root, or any process with `CAP_SYS_PTRACE`.** Kernel-level access reads
  any page. The enclave narrows the attack surface to that; it does not
  pretend to be a hardware enclave.
- **Code running inside the same process.** A malicious dependency shares
  the address space; Rust cannot hide a page from it. What it gains is that
  the secret is never a Python object it can find by walking the heap.
- **The OpenBao export window.** `session/unseal.py` must serialize the
  keys to JSON to save them: `SecretBox.reveal()` exists only for that, the
  `bytearray`s are zeroed immediately, and the immutable base64 text lives
  until the collector frees it. Milliseconds, opt-in, documented.
- **Plaintext content and `DIAGNOS_API_TOKEN`.** Decrypted records and
  file bytes are the product and go back to the caller; the token is a
  bearer credential already present in the environment.
- **Windows.** `VirtualLock` + zero-on-drop only: no guard pages, no
  fork semantics, no dump advisory. `memory_status()` reports it honestly.

## Operating it

Locking pages costs against `RLIMIT_MEMLOCK` (often 64 KiB in a
container). Each box takes one data page plus two guard pages; a session
with a few dozen groups fits in a few hundred KiB. When the kernel refuses,
the crate keeps every other protection and counts the refusal;
`warn_if_unlocked()` emits one `MemoryLockWarning` after unlock. Choose the
policy with `DIAGNOS_MEMORY_LOCK`:

| `DIAGNOS_MEMORY_LOCK` | Behaviour |
|---|---|
| `best-effort` (default) | keep running, warn once |
| `require` | `SecureError` on the first page that will not lock — the process refuses to hold keys in swappable memory |

To make locking succeed as a non-root user: raise `ulimit -l`, or grant
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

## Layout

```
native/
├── Cargo.toml          pinned RustCrypto/dalek stack, release profile with overflow checks
├── src/
│   ├── lib.rs          #![deny(unsafe_code)] crate root; the pymodule
│   ├── locked/         LockedBuffer: mmap + guard pages + mlock + wipe-on-fork; caps.rs raises CAP_IPC_LOCK per thread
│   ├── secret_box.rs   SecretBox: the Python handle and every operation that uses a key
│   ├── buffer.rs       Python buffers in, zeroizing Rust memory out; writable sources are zeroed
│   ├── kdf.rs           HMAC-SHA512, HKDF-SHA256
│   ├── aead.rs          AES-256-GCM
│   ├── hybrid.rs        X25519 + ML-KEM-768 seal/open, HybridKeyPair, sealed-session parsing
│   ├── secretstream.rs  libsodium crypto_secretstream_xchacha20poly1305, bit-exact, over a locked 44-byte state
│   ├── stream.rs        SecretStreamPush / SecretStreamPull (GIL released per chunk)
│   ├── entropy.rs       EntropyPool: SHA-256(os_random ‖ state ‖ counter), state = SHA-256(seed), all in a locked page
│   ├── process.rs       harden_process(), memory_status() (rlimit/prctl syscalls)
│   ├── rng.rs           the OS CSPRNG as rand_core traits; the crate's only randomness
│   └── error.rs         one Error enum → SecureError (a subclass of diagnos.errors.CryptoError)
└── tests/vectors.rs      the normative vectors in ../tests/vectors, run against the Rust core directly
```

Every primitive is the RustCrypto or dalek implementation; this crate
contains no cryptographic arithmetic of its own except the secretstream
port, which is a line-by-line translation of libsodium's C, proven against
PyNaCl in the Python suite (`sdk/tests/crypto/test_secure*.py`) and against
the vectors here. `ExpandedKeyEncoding` for ML-KEM is used on purpose: the
protocol fixes the FIPS 203 expanded key (`dk_pke ‖ ek ‖ H(ek) ‖ z`, 2400
bytes), the form every other implementation of it emits.

## Build and test

```sh
# from the repository root — the wheel (and this crate) build through uv/maturin
make sync
make lint-rust    # cargo fmt --check + cargo clippy --all-targets -D warnings
make test-rust    # cargo test (unit tests + tests/vectors.rs); PYO3_PYTHON is set by the Makefile
```

`PYO3_PYTHON` must point at a CPython ≥ 3.11 for `cargo test`; the wheel
is `abi3-py311`, one build per platform. The `.so` is not rebuilt by `uv
sync` after a Rust edit — run `uv sync --reinstall-package diagnos`.
