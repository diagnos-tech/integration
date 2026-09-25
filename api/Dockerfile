# 🇺🇸 Image for `diagnos-api`: the FastAPI facade over the diagnos SDK, serving
#    HTTPS with mandatory mutual TLS. Built from the workspace root so the SDK
#    is installed from source, never from a registry that could drift.
# 🇧🇷 Imagem do `diagnos-api`: a fachada FastAPI sobre o SDK diagnos, servindo
#    HTTPS com mTLS obrigatório. Construída da raiz do workspace para o SDK ser
#    instalado do fonte, nunca de um registro que possa divergir.
#
#   docker build -f api/Dockerfile -t diagnos-api .        (from apps/integration)
#   docker run --rm -p 8443:8443 --cap-add=IPC_LOCK \
#     -e DIAGNOS_API_TOKEN=apikey-… \
#     -e DIAGNOS_API_MTLS_CA_FILE=/certs/clients-ca.pem \
#     -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \
#     -v $PWD/certs:/certs:ro diagnos-api
#   `--cap-add=IPC_LOCK` is what lets the SDK lock its keys in RAM past the
#   64 KiB default; without it the container still starts and the SDK runs
#   in best-effort mode with a `MemoryLockWarning` (see the `setcap` note).
# 🇺🇸 Pinned to `-bookworm` rather than the floating `python:3.12-slim` (which
#    now tracks Debian trixie): the Rust toolchain below is copied from a
#    bookworm image, and the enclave's `.so` must link against the exact
#    glibc it will run against in the final stage, not merely a compatible
#    one.
# 🇧🇷 Travado em `-bookworm` em vez do `python:3.12-slim` flutuante (que hoje
#    aponta para o Debian trixie): o toolchain Rust abaixo é copiado de uma
#    imagem bookworm, e o `.so` do enclave precisa linkar contra o glibc
#    exato com que vai rodar no estágio final, não só um compatível.
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/local/bin/uv
# 🇺🇸 Rust toolchain for `uv sync` to build the memory-enclave crate
#    (`sdk/native`, `rust-version = "1.85"`) via maturin. Copied from the
#    official image instead of installed via rustup: same bytes CI verifies,
#    no network fetch of the installer at build time.
# 🇧🇷 Toolchain Rust para o `uv sync` construir o crate do enclave de memória
#    (`sdk/native`, `rust-version = "1.85"`) via maturin. Copiado da imagem
#    oficial em vez de instalado via rustup: os mesmos bytes que a CI
#    verifica, sem buscar o instalador pela rede no build.
COPY --from=rust:1.98.0-slim-bookworm /usr/local/cargo /usr/local/cargo
COPY --from=rust:1.98.0-slim-bookworm /usr/local/rustup /usr/local/rustup
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
# 🇺🇸 `build-essential` supplies `cc`, the linker `cargo`/maturin shell out to
#    for the crate's `cdylib`; the Rust image carries it already, this slim
#    Python one does not.
# 🇧🇷 `build-essential` fornece o `cc`, o linker que `cargo`/maturin chamam
#    para o `cdylib` do crate; a imagem Rust já vem com ele, esta Python
#    slim não.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY sdk ./sdk
COPY cli ./cli
COPY api ./api
# 🇺🇸 Locked, non-editable install into a self-contained venv; builds the
#    Rust enclave into the `diagnos` wheel along the way.
# 🇧🇷 Instalação travada e não-editável num venv autocontido; no caminho,
#    constrói o enclave em Rust dentro do wheel `diagnos`.
RUN uv sync --frozen --no-dev --no-editable --package diagnos-api

FROM python:3.12-slim-bookworm
# 🇺🇸 Non-root, read-only-friendly: the process holds keys only in RAM.
# 🇧🇷 Sem root, amigável a filesystem somente-leitura: o processo só tem chaves na RAM.
RUN useradd --system --uid 10001 --create-home diagnos
COPY --from=build --chown=diagnos:diagnos /workspace/.venv /opt/diagnos
# 🇺🇸 The SDK locks its secrets in RAM with `mlock`; a non-root process can
#    only lock more than the default 64 KiB `RLIMIT_MEMLOCK` with
#    `CAP_IPC_LOCK`. Two things make that work for `diagnos` (uid 10001):
#    the container runtime granting the capability (`cap_add: [IPC_LOCK]`
#    in Compose, `capabilities.add: [IPC_LOCK]` in Kubernetes) and this file
#    capability on the interpreter, which turns the grant into a capability
#    the process actually holds. `+p` (permitted), deliberately not `+ep`:
#    with the effective bit set the kernel refuses to exec a binary whose
#    file capabilities exceed the container's bounding set — `EPERM` before
#    the first line of Python — so a manifest that forgets the grant would
#    crash-loop. With `+p` the binary always starts; the SDK's enclave
#    raises the capability into the effective set itself
#    (`sdk/native/src/locked/caps.rs`) when it is there, and falls back to
#    best-effort locking with a warning when it is not.
# 🇧🇷 O SDK trava seus segredos na RAM com `mlock`; um processo sem root só
#    consegue travar além do padrão de 64 KiB do `RLIMIT_MEMLOCK` com
#    `CAP_IPC_LOCK`. Duas coisas fazem isso funcionar para `diagnos` (uid
#    10001): o runtime de container conceder a capability (`cap_add:
#    [IPC_LOCK]` no Compose, `capabilities.add: [IPC_LOCK]` no Kubernetes)
#    e esta capability de arquivo no interpretador, que transforma a
#    concessão numa capability que o processo de fato tem. `+p`
#    (permitted), de propósito não `+ep`: com o bit effective o kernel se
#    recusa a executar um binário cujas capabilities de arquivo excedem o
#    bounding set do container — `EPERM` antes da primeira linha de Python
#    — então um manifesto que esquecesse a concessão entraria em
#    crash-loop. Com `+p` o binário sempre sobe; o enclave do SDK sobe a
#    capability para o conjunto effective sozinho
#    (`sdk/native/src/locked/caps.rs`) quando ela está lá, e cai para
#    travamento best-effort com aviso quando não está.
RUN apt-get update && apt-get install -y --no-install-recommends libcap2-bin \
    && setcap cap_ipc_lock=+p "$(readlink -f /usr/local/bin/python3.12)" \
    && apt-get purge -y --auto-remove libcap2-bin \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/diagnos/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    DIAGNOS_API_HOST=0.0.0.0 \
    DIAGNOS_API_PORT=8443
USER diagnos
EXPOSE 8443
ENTRYPOINT ["diagnos-api"]
