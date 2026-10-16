# Install

**English** · [Português (Brasil)](install.pt-BR.md)

One package, `diagnos`, and you install only the layers you use. The CLI and the API stand on the SDK and never
reimplement a byte of it, so whatever you install, the cryptography underneath is the same.

| Install | You get |
|---|---|
| `pip install diagnos` | the base: `diagnos docs`, `version`, `setup` and `help` — no dependencies at all |
| `pip install "diagnos[sdk]"` | the Python SDK — `from diagnos import Diagnos` |
| `pip install "diagnos[cli]"` | the full `diagnos` command line |
| `pip install "diagnos[api]"` | `diagnos-api`, the REST facade — or its signed image, `ghcr.io/diagnos-tech/diagnos-api` |

Extras combine (`"diagnos[cli,api]"`), and two more sit on top: `openbao` (the token in OpenBao, for servers) and
`dev-certs` (`diagnos-api dev-certs`, certificates for a local run). Every layer's code ships in the one wheel; an
extra only adds its dependencies.

## Requirements

| | Supported | Notes |
|---|---|---|
| Python | CPython 3.11, 3.12, 3.13 | the wheel is `abi3`, one build per platform |
| Linux, macOS | full memory protection | locked pages, guard pages, no core dumps, wiped on `fork()` |
| Windows | reduced memory protection | `VirtualLock` and zero-on-drop only — see [the enclave](../../apps/sdk/native/README.md) |
| Rust | only to build from source | wheels from PyPI ship the compiled enclave; a checkout pins the version in `rust-toolchain.toml` |

## Let `diagnos` set it up

The base install knows how to install the rest. Every command is shown before it runs and confirmed once:

```sh
uv tool install diagnos      # or: pipx install diagnos
diagnos setup sdk            # adds the SDK to the Python project in this folder, with uv
diagnos setup cli            # gives this `diagnos` every command, with uv
diagnos setup api            # pulls the API image and verifies its signature, with Docker and cosign
diagnos setup sdk --dry-run  # only prints what it would run
```

A missing `uv` or Docker is never installed for you: `setup` prints its official install page and exits with `69`.

## The SDK

```sh
uv add "diagnos[sdk]"            # in a uv project — or: pip install "diagnos[sdk]"
uv add "diagnos[sdk,openbao]"    # adds hvac, for the token in OpenBao on servers
```

> [!NOTE]
> **Until `0.1.0` is on PyPI**, install from the repository. Building compiles the Rust memory enclave, so you need a
> [Rust toolchain](https://rustup.rs/) on the machine:
>
> ```sh
> pip install "diagnos[sdk] @ git+https://github.com/diagnos-tech/integration@develop"
> ```

Check that the install works and that the enclave loaded:

```python
import diagnos

print(diagnos.__version__)
print(diagnos.memory_status())  # what the memory enclave guarantees on this machine
```

`memory_status()` reports whether secrets can be locked in RAM here. In a container that usually needs a raised
`RLIMIT_MEMLOCK`; [Deploying](../../apps/api/deploy/README.md#memory-locking) explains the settings involved.

## The CLI

```sh
uv tool install "diagnos[cli]"            # or: pipx install "diagnos[cli]"
uv tool install "diagnos[cli,openbao]"    # with OpenBao, for the token on servers
diagnos version
```

A tool installer keeps the CLI in its own virtual environment, so it never collides with the packages of a project
you are working on. `pip install "diagnos[cli]"` works too. The CLI also ships as an image —
`docker run --rm -e DIAGNOS_TOKEN ghcr.io/diagnos-tech/diagnos patients list` — for machines without Python.

## The REST API

The supported way to run `diagnos-api` is its signed image. `diagnos setup api` pulls it, verifies the pulled digest
and prints the hardened `docker run` by digest; by hand:

```sh
docker pull ghcr.io/diagnos-tech/diagnos-api:0.1.0
```

To build it from a checkout instead, from the repository root:

```sh
docker build --target api -t diagnos-api .
```

Running it needs a certificate pair and a client CA — mutual TLS is the only authentication it accepts. The
[REST API guide](api.md) walks through generating them, and [Deploying](../../apps/api/deploy/README.md) covers
Docker Compose and Kubernetes. `pip install "diagnos[api]"` gives the same `diagnos-api` without a container.

## Verify what you install

Every release is built and signed by one workflow, keylessly, with [Sigstore](https://www.sigstore.dev/). PyPI shows
each file's provenance; the GitHub release carries every file with its `.sigstore.json` bundle and `SHA256SUMS`, and
the images are signed by digest. [SECURITY.md](../../SECURITY.md#verifying-a-release) has the exact commands.

## From a checkout, for contributors

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # uv sync --locked: every extra, the dev tools, and the enclave built with cargo
make check   # everything CI runs
```

You need [uv](https://docs.astral.sh/uv/) and [rustup](https://rustup.rs/), which installs the Rust that
`rust-toolchain.toml` pins. `make sync` rebuilds the enclave whenever its sources change.
[CONTRIBUTING.md](../../CONTRIBUTING.md) has the everyday loop.

## Coming from `imgexam`, or from `diagnos-cli` and `diagnos-api`

Packages, the CLI command, the Docker image, environment variables and the OpenBao path prefix were renamed; wire
labels were not. The CLI and the API are now extras of `diagnos`. [MIGRATING.md](../../MIGRATING.md) has the
find/replace checklist.
