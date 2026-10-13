# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# 🇺🇸 The two images of `diagnos`, from one file and the repository root as context:
#
#      docker build --target api -t diagnos-api .     # the REST API (`diagnos[api]`), HTTPS with mandatory mTLS
#      docker build --target cli -t diagnos .         # the full command line (`diagnos[cli,openbao]`)
#
#    Both install one wheel, `diagnos`, into a virtual environment whose every dependency comes from `uv.lock`
#    with its hash checked, and none is built from source. Locally, the `wheels` stage compiles that wheel from
#    this checkout. The release workflow replaces the stage with the wheels it already built, hashed and
#    smoke-tested (`--build-context wheels=<dir>`), so the image carries the very bytes published to PyPI.
#    Every base image is pinned by digest; Dependabot moves tag and digest together.
# 🇧🇷 As duas imagens do `diagnos`, de um arquivo só e com a raiz do repositório como contexto:
#
#      docker build --target api -t diagnos-api .     # a API REST (`diagnos[api]`), HTTPS com mTLS obrigatório
#      docker build --target cli -t diagnos .         # a linha de comando completa (`diagnos[cli,openbao]`)
#
#    As duas instalam um wheel, `diagnos`, num ambiente virtual cuja dependência vem toda do `uv.lock` com o
#    hash conferido, e nenhuma é construída do fonte. Localmente, o estágio `wheels` compila esse wheel a partir
#    deste checkout. O workflow de release troca o estágio pelos wheels que ele já construiu, conferiu e testou
#    (`--build-context wheels=<dir>`), então a imagem leva exatamente os bytes publicados no PyPI. Toda imagem
#    base é fixada por digest; o Dependabot move tag e digest juntos.

# 🇺🇸 Each base image once, as a literal `FROM image:tag@sha256:…` — the only form Dependabot reads and updates.
#    The uv here is the one CI pins too (`UV_VERSION` in `package.yml`, `.github/actions/setup`): bump them together.
# 🇧🇷 Cada imagem base uma vez, como um `FROM imagem:tag@sha256:…` literal — a única forma que o Dependabot lê e
#    atualiza. O uv daqui é o mesmo que a CI fixa (`UV_VERSION` no `package.yml`, `.github/actions/setup`): suba juntos.
FROM python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS python
FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv

# 🇺🇸 Local builds only: the wheel compiled from this checkout, by the same maturin build `uv build` runs. The Rust
#    image's version is `rust-toolchain.toml`'s.
# 🇧🇷 Só builds locais: o wheel compilado a partir deste checkout, pelo mesmo build do maturin que o `uv build` roda. A
#    versão da imagem Rust é a do `rust-toolchain.toml`.
FROM rust:1.99.0-slim-trixie@sha256:2752b332db73fdbb7dc576f06c82ed1f312005784ef913d7e04a28f5f55dc581 AS compile
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock LICENSE rust-toolchain.toml ./
COPY wrappers/py/README.md wrappers/py/README.md
COPY apps/sdk/native apps/sdk/native
COPY src src
RUN uv build --wheel --out-dir /wheels

FROM scratch AS wheels
COPY --from=compile /wheels/ /

# 🇺🇸 Where the virtual environments are assembled: uv exists here and never reaches a final image. `uv export`
#    turns the lock into hashed requirements, so a dependency whose bytes changed fails the build, and
#    `--no-build` refuses anything that would have to compile. Then the one `diagnos` wheel, from `wheels` only.
# 🇧🇷 Onde os ambientes virtuais são montados: o uv existe aqui e nunca chega a uma imagem final. O `uv export`
#    transforma o lock em requisitos com hash, então uma dependência cujos bytes mudaram derruba o build, e o
#    `--no-build` recusa qualquer coisa que precisaria compilar. Depois o único wheel `diagnos`, só de `wheels`.
FROM python AS installer
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock ./

FROM installer AS venv-api
RUN --mount=from=wheels,target=/wheels \
    uv export --frozen --no-dev --no-emit-project --extra api --format requirements-txt --output-file req.txt \
    && uv venv /opt/diagnos --python /usr/local/bin/python3 \
    && uv pip install --python /opt/diagnos --require-hashes --no-build --requirements req.txt \
    && uv pip install --python /opt/diagnos --no-deps --no-index --find-links /wheels diagnos

FROM installer AS venv-cli
RUN --mount=from=wheels,target=/wheels \
    uv export --frozen --no-dev --no-emit-project --extra cli --extra openbao --format requirements-txt \
       --output-file req.txt \
    && uv venv /opt/diagnos --python /usr/local/bin/python3 \
    && uv pip install --python /opt/diagnos --require-hashes --no-build --requirements req.txt \
    && uv pip install --python /opt/diagnos --no-deps --no-index --find-links /wheels diagnos

# 🇺🇸 What both images share: the interpreter, a numeric non-root user, and nothing that can build or install.
#    Files are root-owned and read-only to that user: a compromised process cannot rewrite its own code.
# 🇧🇷 O que as duas imagens compartilham: o interpretador, um usuário numérico sem root, e nada que construa ou
#    instale. Os arquivos são do root e só leitura para esse usuário: um processo comprometido não reescreve o próprio código.
FROM python AS runtime
LABEL org.opencontainers.image.source="https://github.com/diagnos-tech/integration" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="diagnos" \
      org.opencontainers.image.documentation="https://dev.diagnos.health"
RUN useradd --system --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin diagnos \
    && python -m pip uninstall --yes --quiet --root-user-action=ignore pip
ENV PATH="/opt/diagnos/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

FROM runtime AS api
LABEL org.opencontainers.image.title="diagnos-api" \
      org.opencontainers.image.description="REST facade (FastAPI, mandatory mTLS) over the diagnos zero-knowledge SDK"
COPY --from=venv-api /opt/diagnos /opt/diagnos
# 🇺🇸 The SDK locks its secrets in RAM with `mlock`. Above the default 64 KiB `RLIMIT_MEMLOCK` a non-root process
#    needs either a raised limit (`--ulimit memlock=-1:-1`, Compose `ulimits`, the reliable way) or
#    `CAP_IPC_LOCK`. This file capability turns a granted `cap_add: [IPC_LOCK]` into one the process holds — but
#    the kernel ignores it under `no-new-privileges`, which every manifest here sets, so it is a fallback, not the
#    mechanism. `+p` (permitted), deliberately not `+ep`: with the effective bit the kernel refuses to exec a binary
#    whose file capabilities exceed the container's bounding set, and a manifest that forgets the grant would
#    crash-loop. The enclave raises the capability itself when it is there (`apps/sdk/native/src/locked/caps.rs`)
#    and falls back to best-effort locking with a warning when it is not.
# 🇧🇷 O SDK trava seus segredos na RAM com `mlock`. Acima do `RLIMIT_MEMLOCK` padrão de 64 KiB, um processo sem
#    root precisa de um limite maior (`--ulimit memlock=-1:-1`, `ulimits` no Compose, o jeito confiável) ou da
#    `CAP_IPC_LOCK`. Esta capability de arquivo transforma um `cap_add: [IPC_LOCK]` concedido em uma que o processo
#    tem — mas o kernel a ignora sob `no-new-privileges`, que todo manifesto daqui define, então ela é um recurso
#    de reserva, não o mecanismo. `+p` (permitted), de propósito não `+ep`: com o bit effective o kernel se recusa
#    a executar um binário cujas capabilities de arquivo excedem o bounding set do container, e um manifesto que
#    esquecesse a concessão entraria em crash-loop. O enclave sobe a capability sozinho quando ela está lá
#    (`apps/sdk/native/src/locked/caps.rs`) e cai para travamento best-effort com aviso quando não está.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libcap2-bin \
    && setcap cap_ipc_lock=+p "$(readlink -f /usr/local/bin/python3)" \
    && apt-get purge --yes --auto-remove libcap2-bin \
    && rm -rf /var/lib/apt/lists/*
ENV DIAGNOS_API_HOST=0.0.0.0 \
    DIAGNOS_API_PORT=8443
USER 10001:10001
EXPOSE 8443
# 🇺🇸 mTLS turns away a plain HTTP probe, so health is "the port accepts connections" — no shell, no client cert.
# 🇧🇷 O mTLS recusa uma sonda HTTP simples, então saúde é "a porta aceita conexões" — sem shell, sem certificado.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8443), 2).close()"]
ENTRYPOINT ["diagnos-api"]

FROM runtime AS cli
LABEL org.opencontainers.image.title="diagnos" \
      org.opencontainers.image.description="The diagnos vault from your terminal: the full diagnos command line"
COPY --from=venv-cli /opt/diagnos /opt/diagnos
# 🇺🇸 One process per `docker run`: a background session agent would die with the container, so it stays off.
#    Keep a session across runs with OpenBao auto-unseal instead (`OPENBAO_ADDR`, `diagnos[openbao]` is in).
# 🇧🇷 Um processo por `docker run`: um agente de sessão em segundo plano morreria com o container, então fica
#    desligado. Para manter a sessão entre execuções, use o auto-unseal do OpenBao (`OPENBAO_ADDR`, o
#    `diagnos[openbao]` está incluído).
ENV DIAGNOS_AGENT=off
# 🇺🇸 The one writable place: mount a folder here for uploads and downloads (`-v "$PWD:/work"`).
# 🇧🇷 O único lugar gravável: monte uma pasta aqui para uploads e downloads (`-v "$PWD:/work"`).
RUN install --directory --owner 10001 --group 10001 --mode 0700 /work
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["diagnos"]
CMD ["--help"]
