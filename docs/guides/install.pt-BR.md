# Instalação

[English](install.md) · **Português (Brasil)**

Um pacote, `diagnos`, e você instala só as camadas que usa. A CLI e a API se apoiam no SDK e nunca reimplementam um
byte dele, então o que quer que você instale, a criptografia por baixo é a mesma.

| Instale | Você ganha |
|---|---|
| `pip install diagnos` | a base: `diagnos docs`, `version`, `setup` e `help` — sem dependência nenhuma |
| `pip install "diagnos[sdk]"` | o SDK Python — `from diagnos import Diagnos` |
| `pip install "diagnos[cli]"` | a linha de comando `diagnos` completa |
| `pip install "diagnos[api]"` | o `diagnos-api`, a fachada REST — ou a imagem assinada dela, `ghcr.io/diagnos-tech/diagnos-api` |

Os extras se combinam (`"diagnos[cli,api]"`), e mais dois ficam por cima: `openbao` (auto-unseal com OpenBao para
servidores) e `dev-certs` (`diagnos-api dev-certs`, certificados para rodar local). O código de toda camada vem no
único wheel; um extra só soma as dependências dela.

## Requisitos

| | Suportado | Observações |
|---|---|---|
| Python | CPython 3.11, 3.12, 3.13 | o wheel é `abi3`, um build por plataforma |
| Linux, macOS | proteção de memória completa | páginas travadas, páginas de guarda, sem core dump, apagado no `fork()` |
| Windows | proteção de memória reduzida | só `VirtualLock` e zerar ao liberar — veja [o enclave](../../apps/sdk/native/README.pt-BR.md) |
| Rust | só para construir do fonte | os wheels do PyPI trazem o enclave compilado; um checkout fixa a versão no `rust-toolchain.toml` |

## Deixe o `diagnos` configurar

A instalação base sabe instalar o resto. Todo comando é mostrado antes de rodar e confirmado uma vez:

```sh
uv tool install diagnos      # ou: pipx install diagnos
diagnos setup sdk            # soma o SDK ao projeto Python desta pasta, com uv
diagnos setup cli            # dá a este `diagnos` todos os comandos, com uv
diagnos setup api            # baixa a imagem da API e verifica a assinatura, com Docker e cosign
diagnos setup sdk --dry-run  # só imprime o que rodaria
```

Um `uv` ou Docker ausente nunca é instalado por você: o `setup` imprime a página oficial de instalação e sai com
`69`.

## O SDK

```sh
uv add "diagnos[sdk]"            # num projeto uv — ou: pip install "diagnos[sdk]"
uv add "diagnos[sdk,openbao]"    # soma o hvac, para o auto-unseal com OpenBao em servidores
```

> [!NOTE]
> **Até a `0.1.0` estar no PyPI**, instale a partir do repositório. O build compila o enclave de memória em Rust,
> então você precisa de um [toolchain Rust](https://rustup.rs/) na máquina:
>
> ```sh
> pip install "diagnos[sdk] @ git+https://github.com/diagnos-tech/integration@develop"
> ```

Confira que a instalação funciona e que o enclave carregou:

```python
import diagnos

print(diagnos.__version__)
print(diagnos.memory_status())  # o que o enclave de memória garante nesta máquina
```

O `memory_status()` diz se os segredos podem ser travados na RAM aqui. Num container isso normalmente precisa de um
`RLIMIT_MEMLOCK` maior; [Implantação](../../apps/api/deploy/README.pt-BR.md#travamento-de-memória) explica as
configurações envolvidas.

## A CLI

```sh
uv tool install "diagnos[cli]"            # ou: pipx install "diagnos[cli]"
uv tool install "diagnos[cli,openbao]"    # com auto-unseal via OpenBao
diagnos version
```

Um instalador de ferramentas mantém a CLI no próprio ambiente virtual, para ela nunca colidir com os pacotes de um
projeto em que você esteja trabalhando. `pip install "diagnos[cli]"` também funciona. A CLI também sai como imagem —
`docker run --rm -e DIAGNOS_TOKEN ghcr.io/diagnos-tech/diagnos patients list` — para máquinas sem Python.

## A API REST

O jeito suportado de rodar o `diagnos-api` é a imagem assinada dele. O `diagnos setup api` a baixa, verifica o digest
baixado e imprime o `docker run` endurecido pelo digest; à mão:

```sh
docker pull ghcr.io/diagnos-tech/diagnos-api:0.1.0
```

Para construí-la a partir de um checkout, da raiz do repositório:

```sh
docker build --target api -t diagnos-api .
```

Rodá-la precisa de um par de certificados e de uma CA de clientes — mTLS é a única autenticação que ela aceita. O
[guia da API REST](api.pt-BR.md) mostra como gerá-los, e o [Implantação](../../apps/api/deploy/README.pt-BR.md) cobre
Docker Compose e Kubernetes. `pip install "diagnos[api]"` dá o mesmo `diagnos-api` sem container.

## Verifique o que você instala

Todo release é construído e assinado por um único workflow, sem chave, com o [Sigstore](https://www.sigstore.dev/).
O PyPI mostra a proveniência de cada arquivo; o release no GitHub traz todo arquivo com o bundle `.sigstore.json` e o
`SHA256SUMS`, e as imagens são assinadas pelo digest. O [SECURITY.pt-BR.md](../../SECURITY.pt-BR.md#verificando-um-release)
tem os comandos exatos.

## A partir de um checkout, para quem contribui

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # uv sync --locked: todo extra, as ferramentas de dev e o enclave construído com cargo
make check   # tudo que a CI roda
```

Você precisa do [uv](https://docs.astral.sh/uv/) e do [rustup](https://rustup.rs/), que instala o Rust que o
`rust-toolchain.toml` fixa. O `make sync` reconstrói o enclave sempre que as fontes dele mudam. O
[CONTRIBUTING.pt-BR.md](../../CONTRIBUTING.pt-BR.md) tem o ciclo do dia a dia.

## Vindo do `imgexam`, ou do `diagnos-cli` e do `diagnos-api`

Pacotes, o comando da CLI, a imagem Docker, variáveis de ambiente e o prefixo de caminho do OpenBao foram
renomeados; rótulos de wire não. A CLI e a API agora são extras do `diagnos`. O
[MIGRATING.pt-BR.md](../../MIGRATING.pt-BR.md) tem o checklist de buscar/substituir.
