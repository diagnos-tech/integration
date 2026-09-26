# Instalação

[English](install.md) · **Português (Brasil)**

Três pacotes, uma forma de instalar cada um. A CLI e a API dependem do SDK e nunca reimplementam um byte dele, então,
o que quer que você instale, a criptografia por baixo é a mesma.

| Pacote | O que é | Instalação |
|---|---|---|
| `diagnos` | o SDK Python — tudo mora aqui | `pip install diagnos` |
| `diagnos-cli` | o comando `diagnos` | `pipx install diagnos-cli` |
| `diagnos-api` | uma fachada REST para sistemas que falam HTTP | a imagem Docker |

## Requisitos

| | Suportado | Observações |
|---|---|---|
| Python | CPython 3.11, 3.12, 3.13 | o wheel é `abi3`, um build por plataforma |
| Linux, macOS | proteção de memória completa | páginas travadas, guard pages, sem core dump, zeradas no `fork()` |
| Windows | proteção de memória reduzida | só `VirtualLock` e zerar ao descartar — veja [o enclave](../../apps/sdk/native/README.pt-BR.md) |
| Rust (stable) | só para construir do código-fonte | os wheels do PyPI já trazem o enclave compilado |

## O SDK

```sh
pip install diagnos
pip install "diagnos[openbao]"   # acrescenta o hvac, para auto-unseal com OpenBao em servidores
```

> [!NOTE]
> **Ainda não está no PyPI.** Até o primeiro release, instale a partir do repositório. Construir o SDK compila o
> enclave de memória em Rust, então você precisa de um [toolchain Rust](https://rustup.rs/) na máquina:
>
> ```sh
> pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```

Confira que a instalação funciona e que o enclave carregou:

```python
import diagnos

print(diagnos.__version__)
print(diagnos.memory_status())  # o que o enclave de memória garante nesta máquina
```

`memory_status()` informa se segredos podem ser travados na RAM aqui. Num container isso em geral precisa de
`CAP_IPC_LOCK`; [Implantação](../../apps/api/deploy/README.pt-BR.md#travamento-de-memória) explica as três
configurações envolvidas.

## A CLI

```sh
pipx install diagnos-cli
pipx install "diagnos-cli[openbao]"   # com auto-unseal via OpenBao
diagnos --version
```

> [!NOTE]
> Até o primeiro release, instale a CLI e o SDK de que ela depende a partir do repositório, num comando só:
>
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```

O `pipx` mantém a CLI no próprio ambiente virtual, então ela nunca colide com os pacotes de um projeto em que você
está trabalhando. `pip install diagnos-cli` também funciona.

## A API REST

A forma suportada de rodar o `diagnos-api` é a imagem Docker, que constrói o SDK, a CLI e a API a partir do
código-fonte, enclave incluso:

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
docker build -f apps/api/Dockerfile -t diagnos-api .
```

Rodá-la exige um par de certificados e uma CA de clientes — TLS mútuo é a única autenticação que ela aceita. O
[guia da API REST](api.pt-BR.md) mostra como gerá-los, e [Implantação](../../apps/api/deploy/README.pt-BR.md) cobre
Docker Compose e Kubernetes.

## De um checkout, para quem contribui

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # uv sync --all-packages: os três pacotes, as ferramentas de dev e o enclave construído com cargo
make check   # tudo que a CI roda
```

Você precisa do [uv](https://docs.astral.sh/uv/) e de Rust. Depois de editar o enclave Rust, `uv sync
--reinstall-package diagnos` o reconstrói. O [CONTRIBUTING.pt-BR.md](../../CONTRIBUTING.pt-BR.md) tem o ciclo do dia
a dia.

## Vindo do `imgexam`

Pacotes, o comando da CLI, a imagem Docker, variáveis de ambiente e o prefixo de path do OpenBao foram renomeados;
rótulos de fio, não. O [MIGRATING.pt-BR.md](../../MIGRATING.pt-BR.md) tem o checklist de localizar/substituir.
