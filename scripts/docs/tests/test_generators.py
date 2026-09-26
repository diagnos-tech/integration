"""🇺🇸 The three generators emit the contract's shapes, deterministically, with ids the site can route.

The shapes are the TypeScript types of `reference.ts`, checked field by
field; determinism is "build twice, render twice, same bytes" — the
property `make docs-check` rests on.

🇧🇷 Os três geradores emitem as formas do contrato, de forma determinística, com ids que o site consegue rotear.

As formas são os tipos TypeScript de `reference.ts`, conferidos campo a
campo; determinismo é "gerar duas vezes, renderizar duas vezes, mesmos
bytes" — a propriedade em que o `make docs-check` se apoia.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.docs import cli, openapi, sdk
from scripts.docs.generate import GENERATORS
from scripts.docs.output import render
from scripts.docs.site import PAGE_ID
from scripts.docs.urls import reference_ids, slugify

SDK_KINDS = {"class", "function", "exception", "method", "property", "attribute"}


def assert_l10n(value: Any) -> None:
    """🇺🇸 `{"en": str, "pt-br": str}` and nothing else. 🇧🇷 `{"en": str, "pt-br": str}` e mais nada."""
    assert isinstance(value, dict)
    assert set(value) == {"en", "pt-br"}
    assert all(isinstance(text, str) for text in value.values())


def assert_generated_from(value: Any, package: str) -> None:
    """🇺🇸 The contract's `GeneratedFrom`. 🇧🇷 O `GeneratedFrom` do contrato."""
    assert set(value) == {"package", "version", "commit"}
    assert value["package"] == package
    assert isinstance(value["version"], str)


@pytest.fixture(scope="module")
def cli_document() -> dict[str, Any]:
    """🇺🇸 One `cli.json`, built once for the module. 🇧🇷 Um `cli.json`, gerado uma vez por módulo."""
    return cli.build()


@pytest.fixture(scope="module")
def sdk_document() -> dict[str, Any]:
    """🇺🇸 One `sdk.json`, built once for the module. 🇧🇷 Um `sdk.json`, gerado uma vez por módulo."""
    return sdk.build()


def test_cli_json_has_the_contract_shape(cli_document: dict[str, Any]) -> None:
    """🇺🇸 `CliReference`, `CliCommand`, `CliParam`, `CliExample`. 🇧🇷 As formas da CLI no contrato."""
    assert cli_document["schemaVersion"] == 1
    assert_generated_from(cli_document["generatedFrom"], "diagnos-cli")
    assert cli_document["program"]["name"] == "diagnos"
    assert_l10n(cli_document["program"]["help"])
    paths = [tuple(command["path"]) for command in cli_document["commands"]]
    assert paths[0] == () and ("patients", "list") in paths and len(paths) == len(set(paths))
    for command in cli_document["commands"]:
        assert set(command) <= {"path", "help", "params", "examples", "untranslated"}
        assert_l10n(command["help"])
        for param in command["params"]:
            assert set(param) == {"name", "kind", "flags", "type", "required", "default", "help"}
            assert param["kind"] in {"argument", "option"}
            assert (param["kind"] == "argument") == (param["flags"] == [])
            assert param["default"] is None or isinstance(param["default"], str)
            assert_l10n(param["help"])
        for example in command.get("examples", []):
            assert example["command"].startswith("diagnos")
            assert_l10n(example["description"])


def test_cli_json_carries_what_help_shows(cli_document: dict[str, Any]) -> None:
    """🇺🇸 A known option, its secondary flag, a hidden default and an example, as the terminal shows them.

    🇧🇷 Uma opção conhecida, a flag secundária, um padrão escondido e um exemplo, como o terminal os mostra.
    """
    by_path = {tuple(command["path"]): command for command in cli_document["commands"]}
    root = {param["name"]: param for param in by_path[()]["params"]}
    assert root["quiet"]["flags"] == ["--quiet", "-q"] and root["quiet"]["default"] == "false"
    assert root["token"]["default"] is None
    login = {param["name"]: param for param in by_path[("login",)]["params"]}
    assert login["auto-unseal"]["flags"] == ["--auto-unseal", "--no-auto-unseal"]
    upload = {param["name"]: param for param in by_path[("files", "upload")]["params"]}
    assert upload["paths"]["type"] == "list[path]" and upload["paths"]["required"]
    assert by_path[("login",)]["examples"][0] == {
        "command": "diagnos login",
        "description": {
            "en": "Prints a link and a code, waits for approval",
            "pt-br": "Imprime link e código, espera a aprovação",
        },
    }


def test_sdk_json_has_the_contract_shape(sdk_document: dict[str, Any]) -> None:
    """🇺🇸 `SdkReference`, `SdkModule`, `SdkMember`, recursively. 🇧🇷 As formas do SDK no contrato, recursivas."""
    assert sdk_document["schemaVersion"] == 1
    assert_generated_from(sdk_document["generatedFrom"], "diagnos")
    [module] = sdk_document["modules"]
    assert module["name"] == "diagnos"
    assert_l10n(module["doc"])

    def check(member: dict[str, Any]) -> None:
        """🇺🇸 One member and its children. 🇧🇷 Um membro e os filhos."""
        assert member["kind"] in SDK_KINDS
        assert set(member) <= {"kind", "name", "signature", "doc", "untranslated", "bases", "members"}
        assert_l10n(member["doc"])
        for child in member.get("members", []):
            check(child)

    for member in module["members"]:
        check(member)


def test_sdk_json_follows_all_in_order(sdk_document: dict[str, Any]) -> None:
    """🇺🇸 Exactly `__all__` minus dunders, in its order. 🇧🇷 Exatamente o `__all__` sem dunders, na ordem dele."""
    import diagnos

    names = [member["name"] for member in sdk_document["modules"][0]["members"]]
    assert names == [name for name in diagnos.__all__ if not name.startswith("__")]


def test_sdk_json_documents_what_a_reader_needs(sdk_document: dict[str, Any]) -> None:
    """🇺🇸 Inherited API of private bases, field types, bases by public name, alias docstrings.

    🇧🇷 API herdada de bases privadas, tipos de campo, bases pelo nome público, docstrings de alias.
    """
    members = {member["name"]: member for member in sdk_document["modules"][0]["members"]}
    drive = {child["name"]: child for child in members["Drive"]["members"]}
    assert "download" in drive and drive["download"]["kind"] == "method"
    assert drive["upload"]["signature"].startswith("(source: str | os.PathLike[str] | bytes | BinaryIO")
    record = {child["name"]: child for child in members["PatientRecord"]["members"]}
    assert record["legal_name"]["signature"] == ": str"
    assert members["PatientRecord"]["bases"] == ["BaseModel"]
    assert members["ValidationError"]["kind"] == "exception" and members["ValidationError"]["members"] == []
    assert members["TimePrecision"]["kind"] == "attribute" and members["TimePrecision"]["doc"]["en"]
    assert " at 0x" not in render(sdk_document, sort_keys=True)


def test_openapi_is_fastapis_with_bilingual_operations() -> None:
    """🇺🇸 OpenAPI 3.1, readable operation ids, no untranslated text. 🇧🇷 OpenAPI 3.1, ids legíveis, sem texto cru."""
    document = openapi.build()
    assert document["openapi"].startswith("3.1")
    assert openapi.untranslated(document) == []
    operation_ids = [op["operationId"] for item in document["paths"].values() for op in item.values()]
    assert "list_patients" in operation_ids and len(operation_ids) == len(set(operation_ids))


@pytest.mark.parametrize("kind", sorted(GENERATORS))
def test_generators_are_deterministic(kind: str) -> None:
    """🇺🇸 Two builds render to the same bytes, with one trailing newline. 🇧🇷 Duas gerações, os mesmos bytes."""
    build, sort_keys = GENERATORS[kind]
    first, second = render(build(), sort_keys=sort_keys), render(build(), sort_keys=sort_keys)
    assert first == second
    assert first.endswith("}\n") and not first.endswith("\n\n")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Diagnos", "diagnos"),
        ("patients list", "patients-list"),
        ("get_node", "get-node"),
        ("", "item"),
        ("EnrollmentDeniedError", "enrollment-denied-error"),
    ],
)
def test_slugify_matches_urls_ts(value: str, expected: str) -> None:
    """🇺🇸 The cases of `urls.test.ts`, and each fits `PAGE_ID`. 🇧🇷 Os casos de `urls.test.ts`, todos no `PAGE_ID`."""
    assert slugify(value) == expected
    assert PAGE_ID.match(f"cli/reference/{slugify(value)}")


def test_every_generated_page_id_is_valid_and_unique(
    cli_document: dict[str, Any], sdk_document: dict[str, Any]
) -> None:
    """🇺🇸 The ids the site will build from each reference. 🇧🇷 Os ids que o site vai montar de cada referência."""
    for section, kind, document in (
        ("cli/reference", "cli", cli_document),
        ("sdk/reference", "sdk", sdk_document),
        ("api/reference", "openapi", openapi.build()),
    ):
        ids = reference_ids(section, kind, document)
        assert ids and all(PAGE_ID.match(page_id) for page_id in ids)
        assert len(ids) == len(set(ids))
