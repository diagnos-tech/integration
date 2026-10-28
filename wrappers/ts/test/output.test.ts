/**
 * 🇺🇸 Output: escaping outside text, aligned tables, when color is on, and the npm ↔ PyPI version spelling.
 *
 * 🇧🇷 Saída: escape de texto de fora, tabelas alinhadas, quando a cor liga, e a grafia de versão npm ↔ PyPI.
 *
 * @module
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { colorWanted, Output, printable, table } from "../src/output.ts";
import { pythonRelease, RELEASE, requirement } from "../src/release.ts";
import { recorder } from "./helpers.ts";

test("printable leaves ordinary text alone, spaces and accents included", () => {
    assert.equal(printable("/home/joão/my project · ok 🙂"), "/home/joão/my project · ok 🙂");
});

test("printable escapes what a terminal would act on, as Python's unicode_escape does", () => {
    assert.equal(printable("a\x1b[31mb"), "a\\x1b[31mb");
    assert.equal(printable("line\nnext\tcol\r"), "line\\nnext\\tcol\\r");
    assert.equal(printable("evil‮txt.exe"), "evil\\u202etxt.exe");
    assert.equal(printable("no break"), "no\\xa0break");
    assert.equal(printable("tag\u{e0001}"), "tag\\U000e0001");
    assert.equal(printable("half\ud800"), "half\\ud800");
});

test("table aligns every column but the last, counting characters, not bytes", () => {
    assert.deepEqual(
        table([
            ["sdk", "installed · instalado", ""],
            ["dev-certs", "not installed", "diagnos setup"],
        ]),
        ["  sdk        installed · instalado", "  dev-certs  not installed          diagnos setup"],
    );
    assert.deepEqual(table([]), []);
});

test("color needs a terminal, no NO_COLOR and no dumb TERM; legacy Windows consoles get none", () => {
    const tty = recorder(true);
    assert.equal(colorWanted(tty, {}, "linux"), true);
    assert.equal(colorWanted(recorder(false), {}, "linux"), false);
    assert.equal(colorWanted(tty, { NO_COLOR: "1" }, "linux"), false);
    assert.equal(colorWanted(tty, { TERM: "dumb" }, "linux"), false);
    assert.equal(colorWanted(tty, {}, "win32"), false);
    assert.equal(colorWanted(tty, { WT_SESSION: "x" }, "win32"), true);
});

test("style wraps text only when color is on", () => {
    assert.equal(new Output(recorder(), recorder()).style("x", "bold"), "x");
    assert.equal(new Output(recorder(), recorder(), { color: true }).style("x", "bold", "red"), "\x1b[1;31mx\x1b[0m");
});

test("data prints indented JSON, non-ASCII as is", () => {
    const stdout = recorder();
    new Output(stdout, recorder()).data({ a: { name: "São" } });
    assert.equal(stdout.text, '{\n  "a": {\n    "name": "São"\n  }\n}\n');
});

test("npm versions map to PyPI's spelling; anything else is a development build", () => {
    assert.equal(pythonRelease("0.1.0"), "0.1.0");
    assert.equal(pythonRelease("0.2.0-rc.1"), "0.2.0rc1");
    assert.equal(pythonRelease("1.0.0-b.2"), "1.0.0b2");
    assert.equal(pythonRelease("0.2.0-dev.3"), null);
    assert.equal(pythonRelease("0.2.0-rc1"), null);
    for (const release of ["0.1.0", "0.2.0rc1"]) {
        assert.match(release, RELEASE);
    }
    assert.equal(requirement("cli", "0.1.0"), "diagnos[cli]==0.1.0");
    assert.equal(requirement("cli", null), "diagnos[cli]");
});
