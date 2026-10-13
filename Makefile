# 🇺🇸 One entry point for everything a contributor or CI runs. `make` alone
#    lists the targets. `make check` is exactly what CI runs — green here means
#    green there. The Rust enclave (`apps/sdk/native`) is built by `make sync` and
#    linted/tested alongside the Python package; `PYO3_PYTHON` points cargo at
#    the project's interpreter so `cargo test` links the same CPython the wheel
#    is built for. Each test suite runs in its own pytest process: they import
#    their helpers by bare name, and two `conftest.py` in one run would collide.
# 🇧🇷 Um ponto de entrada para tudo que quem contribui ou a CI roda. `make`
#    sozinho lista os alvos. `make check` é exatamente o que a CI roda — verde
#    aqui é verde lá. O enclave Rust (`apps/sdk/native`) é construído pelo `make
#    sync` e lintado/testado junto com o pacote Python; `PYO3_PYTHON` aponta
#    o cargo para o interpretador do projeto, para o `cargo test` linkar o
#    mesmo CPython para o qual o wheel é construído. Cada suíte de teste roda no
#    próprio processo do pytest: elas importam os helpers pelo nome, e dois
#    `conftest.py` numa execução só colidiriam.

.DEFAULT_GOAL := help
.PHONY: help sync fmt lint lint-py lint-rust lint-docs types test test-py test-rust cov contract contract-check docs docs-check check fuzz hooks clean

NATIVE := apps/sdk/native/Cargo.toml
# 🇺🇸 Keep in sync with FUZZ_TOOLCHAIN in .github/workflows/fuzz.yml. 🇧🇷 Mantenha igual ao FUZZ_TOOLCHAIN do fuzz.yml.
FUZZ_TOOLCHAIN := nightly-2026-10-12
FUZZ_TARGET ?= secretstream_pull
CARGO_ENV = PYO3_PYTHON="$$(uv run python -c 'import sys; print(sys.executable)')"

help: ## 🇺🇸 List the targets · 🇧🇷 Lista os alvos
	@awk 'BEGIN {FS = ":.*## "; printf "\nUsage · Uso: make <target>\n\n"} \
		/^[a-z][a-z-]+:.*## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n"

sync: ## 🇺🇸 Install every extra, editable, and build the Rust enclave · 🇧🇷 Instala todo extra e constrói o enclave
	uv sync --locked

fmt: ## 🇺🇸 Auto-format and auto-fix Python and Rust · 🇧🇷 Formata e corrige Python e Rust
	uv run ruff check --fix .
	uv run ruff format .
	cargo fmt --manifest-path $(NATIVE)

lint: lint-py lint-rust lint-docs ## 🇺🇸 Every static check (no tests) · 🇧🇷 Toda checagem estática (sem testes)

lint-py:
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/check_bilingual.py src apps wrappers contracts scripts
	uv run python scripts/check_file_size.py

lint-rust:
	cargo fmt --manifest-path $(NATIVE) --check
	$(CARGO_ENV) cargo clippy --manifest-path $(NATIVE) --all-targets -- -D warnings

lint-docs:
	uv run python scripts/check_docs.py

types: ## 🇺🇸 mypy --strict: the package, contract tests, scripts · 🇧🇷 mypy --strict: o pacote, contrato, scripts
	uv run mypy src contracts/tests scripts

test: test-py test-rust ## 🇺🇸 Unit tests: every Python layer and Rust · 🇧🇷 Testes unitários: toda camada Python e Rust

test-py:
	uv run pytest wrappers/py/tests
	uv run pytest apps/sdk/tests
	uv run pytest apps/cli/tests
	uv run pytest apps/api/tests
	uv run pytest scripts/docs/tests scripts/tests

test-rust:
	$(CARGO_ENV) cargo test --manifest-path $(NATIVE)

cov: ## 🇺🇸 Unit tests with one combined coverage report (htmlcov/) · 🇧🇷 Testes com um relatório de cobertura combinado
	rm -f .coverage coverage.xml coverage.json
	uv run pytest wrappers/py/tests --cov --cov-report= --cov-fail-under=0
	uv run pytest apps/sdk/tests --cov --cov-append --cov-report= --cov-fail-under=0
	uv run pytest apps/cli/tests --cov --cov-append --cov-report= --cov-fail-under=0
	uv run pytest apps/api/tests --cov --cov-append --cov-report= --cov-fail-under=0
	uv run pytest scripts/docs/tests scripts/tests
	uv run coverage html --quiet --fail-under=0
	uv run coverage xml --quiet --fail-under=0
	uv run coverage json --quiet --fail-under=0
	uv run coverage report

contract: ## 🇺🇸 Pact consumer tests; regenerates contracts/*.json · 🇧🇷 Testes Pact do consumidor; regera contracts/*.json
	uv run pytest contracts/tests

contract-check: ## 🇺🇸 Fail if the committed contract is stale (CI) · 🇧🇷 Falha se o contrato commitado estiver velho (CI)
	uv run pytest contracts/tests --contract-check

docs: ## 🇺🇸 Regenerate docs/reference/*.json from the code · 🇧🇷 Regera docs/reference/*.json a partir do código
	uv run python -m scripts.docs.generate

docs-check: ## 🇺🇸 Fail if the docs drifted from the code (CI) · 🇧🇷 Falha se a doc divergiu do código (CI)
	uv run python -m scripts.docs.check

check: lint types test contract-check docs-check ## 🇺🇸 Everything CI runs · 🇧🇷 Tudo que a CI roda

fuzz: ## 🇺🇸 Fuzz one enclave target for a minute (FUZZ_TARGET=…, needs cargo-fuzz) · 🇧🇷 Fuzz de um alvo do enclave por um minuto
	cd apps/sdk/native && $(CARGO_ENV) cargo +$(FUZZ_TOOLCHAIN) fuzz run $(FUZZ_TARGET) -- -max_total_time=60

hooks: ## 🇺🇸 Run `make lint` before every commit · 🇧🇷 Roda `make lint` antes de todo commit
	uvx pre-commit install

clean: ## 🇺🇸 Remove build, cache and coverage output · 🇧🇷 Remove saída de build, cache e cobertura
	rm -rf .coverage coverage.xml coverage.json htmlcov contracts/.pact-raw dist build
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	cargo clean --manifest-path $(NATIVE)
