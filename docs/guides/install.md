# Install

**English** · [Português (Brasil)](install.pt-BR.md)

Three packages, one install story each. The CLI and the API depend on the SDK and never reimplement a byte of it, so
whatever you install, the cryptography underneath is the same.

| Package | What it is | Install |
|---|---|---|
| `diagnos` | the Python SDK — everything lives here | `pip install diagnos` |
| `diagnos-cli` | the `diagnos` command | `pipx install diagnos-cli` |
| `diagnos-api` | a REST facade for systems that speak HTTP | the Docker image |

## Requirements

| | Supported | Notes |
|---|---|---|
| Python | CPython 3.11, 3.12, 3.13 | the wheel is `abi3`, one build per platform |
| Linux, macOS | full memory protection | locked pages, guard pages, no core dumps, wiped on `fork()` |
| Windows | reduced memory protection | `VirtualLock` and zero-on-drop only — see [the enclave](../../apps/sdk/native/README.md) |
| Rust (stable) | only to build from source | wheels from PyPI ship the compiled enclave |

## The SDK

```sh
pip install diagnos
pip install "diagnos[openbao]"   # adds hvac, for OpenBao auto-unseal on servers
```

> [!NOTE]
> **Not on PyPI yet.** Until the first release, install from the repository. Building the SDK compiles its Rust
> memory enclave, so you need a [Rust toolchain](https://rustup.rs/) on the machine:
>
> ```sh
> pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```

Check that the install works and that the enclave loaded:

```python
import diagnos

print(diagnos.__version__)
print(diagnos.memory_status())  # what the memory enclave guarantees on this machine
```

`memory_status()` reports whether secrets can be locked in RAM here. In a container that usually needs
`CAP_IPC_LOCK`; [Deploying](../../apps/api/deploy/README.md#memory-locking) explains the three settings involved.

## The CLI

```sh
pipx install diagnos-cli
pipx install "diagnos-cli[openbao]"   # with OpenBao auto-unseal
diagnos --version
```

> [!NOTE]
> Until the first release, install the CLI and the SDK it depends on from the repository in one command:
>
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```

`pipx` keeps the CLI in its own virtual environment, so it never collides with the packages of a project you are
working on. `pip install diagnos-cli` works too.

## The REST API

The supported way to run `diagnos-api` is its Docker image, which builds the SDK, the CLI and the API from source,
enclave included:

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
docker build -f apps/api/Dockerfile -t diagnos-api .
```

Running it needs a certificate pair and a client CA — mutual TLS is the only authentication it accepts. The
[REST API guide](api.md) walks through generating them, and [Deploying](../../apps/api/deploy/README.md) covers
Docker Compose and Kubernetes.

## From a checkout, for contributors

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # uv sync --all-packages: the three packages, the dev tools, and the enclave built with cargo
make check   # everything CI runs
```

You need [uv](https://docs.astral.sh/uv/) and Rust. After editing the Rust enclave, `uv sync --reinstall-package
diagnos` rebuilds it. [CONTRIBUTING.md](../../CONTRIBUTING.md) has the everyday loop.

## Coming from `imgexam`

Packages, the CLI command, the Docker image, environment variables and the OpenBao path prefix were renamed;
wire labels were not. [MIGRATING.md](../../MIGRATING.md) has the find/replace checklist.
