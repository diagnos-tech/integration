# `diagnos._secure` — o enclave de memória

[English](README.md) · **Português (Brasil)**

Um crate Rust pequeno, embarcado no wheel `diagnos` pelo maturin, que guarda
todo segredo que o SDK algum dia tem — chaves de sessão, DEKs de grupo,
chaves de documento, a própria identidade X25519 + ML-KEM-768 do SDK, o pool
de entropia — e executa toda operação que precisa de um. O Python só segura
um handle, `SecretBox`. As mesmas garantias chegam a `diagnos-cli` e
`diagnos-api` de graça: eles nunca tocam uma chave, chamam o SDK.

## Por que Rust, por que aqui

O CPython não consegue prometer onde um segredo mora. `bytes` são
imutáveis e podem ser internados ou copiados por qualquer fatia; um
`bytearray` que cresce deixa o buffer antigo para o coletor; todo objeto fica
numa página de heap que o kernel pode mandar ao swap ou escrever num core
dump; e um `fork()` duplica tudo isso num filho que ninguém auditou. Um
`SecretBox` é uma página que o crate controla: é `mmap`ada anônima,
`mlock`ada para nunca chegar ao swap, excluída de core dumps, zerada num
filho de `fork()`, cercada por guard pages que transformam uma leitura fora
dos limites vinda de qualquer código vizinho numa falha, e zerada com uma
escrita volátil à prova de compilador no instante em que a caixa é
descartada. Nada disso é expressável a partir do Python.

## O que é garantido

| Ameaça | Mecanismo | Onde |
|---|---|---|
| Swap / arquivo de hibernação | `mlock` nas páginas de dados (`VirtualLock` no Windows) | `locked/unix.rs`, `locked/windows.rs` |
| Core dump do processo | `MADV_DONTDUMP` por página + `RLIMIT_CORE = 0` para o processo | `locked/unix.rs`, `process.rs` |
| Attach de `ptrace`/debugger por processo do mesmo uid | `PR_SET_DUMPABLE = 0` (Linux), `PT_DENY_ATTACH` (macOS) | `process.rs` |
| Segredos herdados por um filho de `fork()` | `MADV_WIPEONFORK` + uma palavra sentinela: o filho lê zeros e todo uso lança | `locked/unix.rs`, `locked/mod.rs` |
| Overflow de uma alocação vizinha | Guard page `PROT_NONE` antes e depois dos dados | `locked/unix.rs` |
| Material de chave sobrevivendo em memória liberada | `zeroize` (volátil) ao descartar, em `wipe()`, e em toda cópia Rust transitória (`Zeroizing`) | em todo lugar |
| Vazamento acidental a partir do Python | sem `bytes()`, sem protocolo de buffer, sem indexação, `repr` redigido, sem hash, `pickle`/`copy` recusados, `==` em tempo constante | `secret_box.rs` |
| RNG de VM/container clonado | a semente por resposta do cofre, aberta *dentro* do enclave e misturada em toda DEK e nonce | `entropy.rs`, `secret_box.rs` |

A última linha merece uma frase: nada que o cofre envia como segredo é
lido em Python. O JSON da sessão selada e o JSON de `random_seed` (que viaja
no envelope da resposta, não num header) são decifrados, lidos e
decodificados de base64 em Rust, direto em caixas travadas.

## O que não é

- **Root, ou qualquer processo com `CAP_SYS_PTRACE`.** Acesso em nível de
  kernel lê qualquer página. O enclave estreita a superfície de ataque a
  isso; não finge ser um enclave de hardware.
- **Código rodando dentro do mesmo processo.** Uma dependência maliciosa
  compartilha o espaço de endereços; Rust não consegue esconder uma página
  dela. O que se ganha é que o segredo nunca é um objeto Python que ela
  encontre percorrendo o heap.
- **A janela de exportação do OpenBao.** `session/unseal.py` precisa
  serializar as chaves em JSON para salvá-las: `SecretBox.reveal()` existe
  só para isso, os `bytearray`s são zerados imediatamente, e o texto base64
  imutável vive até o coletor liberá-lo. Milissegundos, opt-in, documentado.
- **Conteúdo em claro e `DIAGNOS_API_TOKEN`.** Registros e bytes de
  arquivo decifrados são o produto e voltam a quem chama; o token é uma
  credencial bearer já presente no ambiente.
- **Windows.** Só `VirtualLock` + zero-ao-descartar: sem guard pages,
  sem semântica de fork, sem aviso de dump. `memory_status()` reporta com
  honestidade.

## Operando

Travar páginas conta contra o `RLIMIT_MEMLOCK` (muitas vezes 64 KiB num
container). Cada caixa ocupa uma página de dados mais duas guard pages; uma
sessão com algumas dezenas de grupos cabe em algumas centenas de KiB. Quando
o kernel recusa, o crate mantém toda outra proteção e conta a recusa;
`warn_if_unlocked()` emite um `MemoryLockWarning` depois do unlock. Escolha a
política com `DIAGNOS_MEMORY_LOCK`:

| `DIAGNOS_MEMORY_LOCK` | Comportamento |
|---|---|
| `best-effort` (padrão) | continua rodando, avisa uma vez |
| `require` | `SecureError` na primeira página que não travar — o processo se recusa a segurar chaves em memória que pode ir ao swap |

Para o travamento dar certo como usuário sem root: aumente `ulimit -l`,
ou conceda `CAP_IPC_LOCK` (`docker run --cap-add IPC_LOCK`, Kubernetes
`capabilities.add: [IPC_LOCK]`) *e* dê ao interpretador a capability de
arquivo `cap_ipc_lock=+p` (`api/Dockerfile` faz). `+p`, não `+ep`: um
binário com o bit effective ligado é recusado pelo kernel (`EPERM` no
`exec`) sempre que o container não recebeu a capability, então um `cap_add`
esquecido viraria crash-loop. Com `+p` o processo sempre sobe e o enclave
sobe a capability para o conjunto effective sozinho, por thread, logo antes
de cada `mlock` (`locked/caps.rs`); sem a concessão, degrada para
best-effort. `memory_status()` reporta `ipc_lock_permitted` e
`ipc_lock_effective`. `DIAGNOS_HARDEN_PROCESS=0` pula o hardening do
processo inteiro (útil só para anexar um debugger).

## Estrutura

```
native/
├── Cargo.toml          stack RustCrypto/dalek travado, perfil release com checagem de overflow
├── src/
│   ├── lib.rs          #![deny(unsafe_code)] raiz do crate; o pymodule
│   ├── locked/         LockedBuffer: mmap + guard pages + mlock + wipe-on-fork; caps.rs sobe CAP_IPC_LOCK por thread
│   ├── secret_box.rs   SecretBox: o handle Python e toda operação que usa uma chave
│   ├── buffer.rs       buffers do Python entram, memória Rust zerada sai; origens graváveis são zeradas
│   ├── kdf.rs           HMAC-SHA512, HKDF-SHA256
│   ├── aead.rs          AES-256-GCM
│   ├── hybrid.rs        selo/abertura X25519 + ML-KEM-768, HybridKeyPair, leitura da sessão selada
│   ├── secretstream.rs  crypto_secretstream_xchacha20poly1305 do libsodium, bit a bit igual, sobre um estado travado de 44 bytes
│   ├── stream.rs        SecretStreamPush / SecretStreamPull (GIL liberado a cada pedaço)
│   ├── entropy.rs       EntropyPool: SHA-256(os_random ‖ estado ‖ contador), estado = SHA-256(semente), tudo numa página travada
│   ├── process.rs       harden_process(), memory_status() (syscalls de rlimit/prctl)
│   ├── rng.rs           o CSPRNG do SO como traits do rand_core; a única aleatoriedade do crate
│   └── error.rs         um enum Error só → SecureError (subclasse de diagnos.errors.CryptoError)
└── tests/vectors.rs      os vetores normativos em ../tests/vectors, rodados direto contra o core Rust
```

Toda primitiva é a implementação do RustCrypto ou do dalek; este crate
não contém aritmética criptográfica própria além do porte do secretstream,
que é uma tradução linha a linha do C do libsodium, provada contra o PyNaCl
na suíte Python (`sdk/tests/crypto/test_secure*.py`) e contra os vetores
aqui. O `ExpandedKeyEncoding` do ML-KEM é usado de propósito: o protocolo
fixa a chave expandida da FIPS 203 (`dk_pke ‖ ek ‖ H(ek) ‖ z`, 2400 bytes), a
forma que toda outra implementação dele emite.

## Build e teste

```sh
# da raiz do repositório — o wheel (e este crate) constroem via uv/maturin
make sync
make lint-rust    # cargo fmt --check + cargo clippy --all-targets -D warnings
make test-rust    # cargo test (testes unitários + tests/vectors.rs); PYO3_PYTHON é definido pelo Makefile
```

`PYO3_PYTHON` precisa apontar para um CPython ≥ 3.11 para o `cargo test`;
o wheel é `abi3-py311`, um build por plataforma. O `.so` não é reconstruído
pelo `uv sync` depois de editar Rust — rode `uv sync --reinstall-package diagnos`.
