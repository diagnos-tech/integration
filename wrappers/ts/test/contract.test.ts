/**
 * 🇺🇸 Conformance: this wrapper implements `wrappers/contract.json` exactly — the spec every wrapper copies.
 *
 * 🇧🇷 Conformidade: este wrapper implementa exatamente o `wrappers/contract.json` — a especificação de todo wrapper.
 *
 * @module
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { COMMANDS } from "../src/app.ts";
import { LINKS } from "../src/docs.ts";
import { EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE } from "../src/exit-codes.ts";
import { DISTRIBUTION } from "../src/release.ts";
import { IMAGE, identity, ISSUER, MIN_COSIGN, TRIGGER } from "../src/setup/image.ts";
import { TARGETS } from "../src/setup/index.ts";
import { INSTALL_PAGES } from "../src/setup/tools.ts";

interface Contract {
    program: string;
    package: { pypi: string; extras: string[] };
    commands: Record<string, { arguments: Record<string, string[]>; options: string[] }>;
    links: Record<string, { name: string; url: string }>;
    setup: Record<string, { requires: string; image?: string; minimumCosign?: string; signer?: Record<string, string> }>;
    installPages: Record<string, string>;
    exitCodes: Record<string, number>;
}

const CONTRACT = JSON.parse(readFileSync(new URL("../../contract.json", import.meta.url), "utf8")) as Contract;
const MANIFEST = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { name: string; bin: Record<string, string> };

test("the command set is the contract's, under the contract's program name", () => {
    assert.deepEqual(Object.keys(COMMANDS).sort(), Object.keys(CONTRACT.commands).sort());
    assert.equal(CONTRACT.program, "diagnos");
    assert.equal(MANIFEST.name, CONTRACT.program);
    assert.deepEqual(Object.keys(MANIFEST.bin), [CONTRACT.program]);
});

for (const [name, expected] of Object.entries(CONTRACT.commands)) {
    test(`\`${name}\` takes exactly the contract's arguments and options`, () => {
        const spec = COMMANDS[name as keyof typeof COMMANDS];
        const positional = spec.positional === undefined ? {} : { [spec.positional.name]: [...spec.positional.choices] };
        assert.deepEqual(positional, expected.arguments);
        assert.deepEqual(new Set(spec.flags.flatMap((flag) => flag.names)), new Set(expected.options));
    });
}

test("`docs --json` prints the contract's links verbatim", () => {
    const shape = Object.fromEntries(LINKS.map((link) => [link.topic, { name: link.name, url: link.url }]));
    assert.deepEqual(shape, CONTRACT.links);
});

test("setup targets, the image, its signer and the install pages are the contract's", () => {
    assert.deepEqual(Object.keys(TARGETS).sort(), Object.keys(CONTRACT.setup).sort());
    const api = CONTRACT.setup.api;
    assert.equal(api?.image, IMAGE);
    assert.equal(api?.signer?.identity?.replace("{version}", "9.9.9"), identity("9.9.9"));
    assert.equal(api?.signer?.issuer, ISSUER);
    assert.equal(api?.signer?.trigger, TRIGGER);
    assert.equal(api?.minimumCosign, MIN_COSIGN.join("."));
    assert.deepEqual(CONTRACT.installPages, INSTALL_PAGES);
});

test("the exit codes are 0, 1, 2 and 69", () => {
    assert.deepEqual(CONTRACT.exitCodes, { ok: EXIT_OK, failed: EXIT_FAILED, usage: EXIT_USAGE, unavailable: EXIT_UNAVAILABLE });
});

test("the Python distribution is the contract's", () => {
    assert.equal(CONTRACT.package.pypi, DISTRIBUTION);
});
