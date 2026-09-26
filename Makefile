# 🇺🇸 One entry point for everything a contributor or CI runs. `make` alone
#    lists the targets. `make check` is exactly what CI runs — green here means
#    green there. The Rust enclave (`apps/sdk/native`) is built by `make sync` and
#    linted/tested alongside the Python packages; `PYO3_PYTHON` points cargo at
#    the workspace interpreter so `cargo test` links the same CPython the wheel
#    is built for.
# 🇧🇷 Um ponto de entrada para tudo que quem contribui ou a CI roda. `make`
#    sozinho lista os alvos. `make check` é exatamente o que a CI roda — verde
#    aqui é verde lá. O enclave Rust (`apps/sdk/native`) é construído pelo `make
#    sync` e lintado/testado junto com os pacotes Python; `PYO3_PYTHON` aponta
#    o cargo para o interpretador do workspace, para o `cargo test` linkar o
#    mesmo CPython para o qual o wheel é construído.

.DEFAULT_GOAL := help
.PHONY: help sync fmt lint lint-py lint-rust lint-docs types test test-py test-rust cov contract contract-check docs docs-check check hooks clean

NATIVE := apps/sdk/native/Cargo.toml
PYTHON_PACKAGES := apps/sdk/src apps/cli/src apps/api/src
CARGO_ENV = PYO3_PYTHON="$$(uv run python -c 'import sys; print(sys.executable)')"

help: ## 🇺🇸 List the targets · 🇧🇷 Lista os alvos
	@awk 'BEGIN {FS = ":.*## "; printf "\nUsage · Uso: make <target>\n\n"} \
		/^[a-z][a-z-]+:.*## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n"

sync: ## 🇺🇸 Install everything and build the Rust enclave · 🇧🇷 Instala tudo e constrói o enclave Rust
	uv sync --all-packages

fmt: ## 🇺🇸 Auto-format and auto-fix Python and Rust · 🇧🇷 Formata e corrige Python e Rust
	uv run ruff check --fix .
	uv run ruff format .
	cargo fmt --manifest-path $(NATIVE)

lint: lint-py lint-rust lint-docs ## 🇺🇸 Every static check (no tests) · 🇧🇷 Toda checagem estática (sem testes)

lint-py:
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/check_bilingual.py apps/sdk apps/cli apps/api contracts scripts

lint-rust:
	cargo fmt --manifest-path $(NATIVE) --check
	$(CARGO_ENV) cargo clippy --manifest-path $(NATIVE) --all-targets -- -D warnings

lint-docs:
	uv run python scripts/check_docs.py

types: ## 🇺🇸 mypy --strict: packages, contract tests, scripts · 🇧🇷 mypy --strict: pacotes, contrato, scripts
	uv run mypy $(PYTHON_PACKAGES) contracts/tests scripts

test: test-py test-rust ## 🇺🇸 Unit tests: Python (3 packages) and Rust · 🇧🇷 Testes unitários: Python (3 pacotes) e Rust

test-py:
	uv run --package diagnos pytest apps/sdk/tests
	uv run --package diagnos-cli pytest apps/cli/tests
	uv run --package diagnos-api pytest apps/api/tests
	uv run pytest scripts/docs/tests

test-rust:
	$(CARGO_ENV) cargo test --manifest-path $(NATIVE)

cov: ## 🇺🇸 Unit tests with one combined coverage report (htmlcov/) · 🇧🇷 Testes com um relatório de cobertura combinado
	rm -f .coverage coverage.xml coverage.json
	uv run --package diagnos pytest apps/sdk/tests --cov --cov-report= --cov-fail-under=0
	uv run --package diagnos-cli pytest apps/cli/tests --cov --cov-append --cov-report= --cov-fail-under=0
	uv run --package diagnos-api pytest apps/api/tests --cov --cov-append --cov-report= --cov-fail-under=0
	uv run pytest scripts/docs/tests
	uv run coverage html --quiet --fail-under=0
	uv run coverage xml --quiet --fail-under=0
	uv run coverage json --quiet --fail-under=0
	uv run coverage report

contract: ## 🇺🇸 Pact consumer tests; regenerates contracts/*.json · 🇧🇷 Testes Pact do consumidor; regera contracts/*.json
	uv run --package diagnos pytest contracts/tests

contract-check: ## 🇺🇸 Fail if the committed contract is stale (CI) · 🇧🇷 Falha se o contrato commitado estiver velho (CI)
	uv run --package diagnos pytest contracts/tests --contract-check

docs: ## 🇺🇸 Regenerate docs/reference/*.json from the code · 🇧🇷 Regera docs/reference/*.json a partir do código
	uv run python -m scripts.docs.generate

docs-check: ## 🇺🇸 Fail if the docs drifted from the code (CI) · 🇧🇷 Falha se a doc divergiu do código (CI)
	uv run python -m scripts.docs.check

check: lint types test contract-check docs-check ## 🇺🇸 Everything CI runs · 🇧🇷 Tudo que a CI roda

hooks: ## 🇺🇸 Run `make lint` before every commit · 🇧🇷 Roda `make lint` antes de todo commit
	uvx pre-commit install

clean: ## 🇺🇸 Remove build, cache and coverage output · 🇧🇷 Remove saída de build, cache e cobertura
	rm -rf .coverage coverage.xml coverage.json htmlcov contracts/.pact-raw dist build
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	cargo clean --manifest-path $(NATIVE)
