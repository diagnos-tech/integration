# 🇺🇸 One entry point for lint, types and tests of the three packages — what CI
#    runs and what a contributor runs before opening a pull request. The Rust
#    enclave (`sdk/native`) is linted and tested here too; `PYO3_PYTHON` points
#    cargo at the workspace interpreter so `cargo test` links the same CPython
#    the wheel is built for.
# 🇧🇷 Um ponto de entrada para lint, tipos e testes dos três pacotes — o que a
#    CI roda e o que quem contribui roda antes de abrir um pull request. O
#    enclave em Rust (`sdk/native`) também é lintado e testado aqui;
#    `PYO3_PYTHON` aponta o cargo para o interpretador do workspace, para o
#    `cargo test` linkar o mesmo CPython para o qual o wheel é construído.
.PHONY: sync lint types test check rust-lint rust-test

NATIVE := sdk/native/Cargo.toml
export PYO3_PYTHON := $(shell uv run python -c 'import sys; print(sys.executable)')

sync:
	uv sync --all-packages

lint: rust-lint
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/check_bilingual.py sdk cli api

rust-lint:
	cargo fmt --manifest-path $(NATIVE) --check
	cargo clippy --manifest-path $(NATIVE) --all-targets -- -D warnings

types:
	uv run mypy sdk/src cli/src api/src

test: rust-test
	uv run --package diagnos pytest sdk/tests
	uv run --package diagnos-cli pytest cli/tests
	uv run --package diagnos-api pytest api/tests

rust-test:
	cargo test --manifest-path $(NATIVE)

check: lint types test
