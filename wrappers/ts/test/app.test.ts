/**
 * 🇺🇸 The command line end to end: help, docs, version, usage errors, and commands handed to the full CLI.
 *
 * 🇧🇷 A linha de comando de ponta a ponta: ajuda, docs, version, erros de uso, e comandos entregues à CLI completa.
 *
 * @module
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { symlinkSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { hoisted, main } from "../src/app.ts";
import { EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE } from "../src/exit-codes.ts";
import { layers, MARKER, ours, reported } from "../src/layers.ts";
import { VERSION } from "../src/release.ts";
import { fakeIo, logged, POSIX, program, pythonDiagnos, searchPath, temp } from "./helpers.ts";

test("no command prints the overview", async () => {
    const io = fakeIo();
    assert.equal(await main([], io), EXIT_OK);
    assert.match(io.stdout.text, new RegExp(`^diagnos ${VERSION.replaceAll(".", "\\.")} — `));
    assert.match(io.stdout.text, /diagnos setup api/);
});

test("--version prints the version alone", async () => {
    const io = fakeIo();
    assert.equal(await main(["--version"], io), EXIT_OK);
    assert.equal(io.stdout.text, `diagnos ${VERSION}\n`);
});

test("global flags typed before the command move after it", () => {
    assert.deepEqual(hoisted(["--json", "--no-color", "docs", "dev"]), ["docs", "--json", "--no-color", "dev"]);
    assert.deepEqual(hoisted(["--json"]), ["--json"]);
});

test("docs lists the three sites; a topic prints its URL alone", async () => {
    const all = fakeIo();
    assert.equal(await main(["docs"], all), EXIT_OK);
    assert.match(all.stdout.text, /^Help Center {8}https:\/\/docs\.diagnos\.health/);
    const one = fakeIo();
    assert.equal(await main(["docs", "trust"], one), EXIT_OK);
    assert.equal(one.stdout.text, "https://trust.diagnos.health\n");
});

test("docs --json prints {topic: {name, url}}, with the flag on either side", async () => {
    const io = fakeIo();
    assert.equal(await main(["--json", "docs", "dev"], io), EXIT_OK);
    assert.deepEqual(JSON.parse(io.stdout.text), { dev: { name: "Developer Central", url: "https://dev.diagnos.health" } });
});

test("docs --open needs a topic, and says so when there is no browser", async () => {
    const bare = fakeIo();
    assert.equal(await main(["docs", "--open"], bare), EXIT_USAGE);
    const headless = fakeIo({ env: { PATH: "" } });
    assert.equal(await main(["docs", "dev", "--open"], headless), EXIT_OK);
    if (process.platform === "linux") {
        assert.match(headless.stderr.text, /No browser here · Sem navegador aqui: https:\/\/dev\.diagnos\.health/);
    }
});

test("a wrong choice or an unknown option is a usage error with argparse's lines", async () => {
    const choice = fakeIo();
    assert.equal(await main(["docs", "nope"], choice), EXIT_USAGE);
    assert.match(choice.stderr.text, /^usage: diagnos docs \[-h\] \[--open\] \[--json\] \[--no-color\] \[\{help,dev,trust\}\]\n/);
    assert.match(choice.stderr.text, /diagnos docs: error: argument topic: invalid choice: 'nope' \(choose from 'help', 'dev', 'trust'\)/);
    const option = fakeIo();
    assert.equal(await main(["setup", "api", "--json"], option), EXIT_USAGE);
    assert.match(option.stderr.text, /unrecognized arguments: --json/);
    const stray = fakeIo();
    assert.equal(await main(["-x"], stray), EXIT_USAGE);
    assert.match(stray.stderr.text, /Unknown option · Opção desconhecida: -x/);
});

test("setup without a target prints its help and exits 2; help <command> prints that command's", async () => {
    const io = fakeIo();
    assert.equal(await main(["setup"], io), EXIT_USAGE);
    assert.match(io.stdout.text, /--dry-run/);
    const help = fakeIo();
    assert.equal(await main(["help", "setup"], help), EXIT_OK);
    assert.match(help.stdout.text, /^usage: diagnos setup /);
    assert.match(help.stdout.text, /--yes, -y +Run without asking/);
    const dash = fakeIo();
    assert.equal(await main(["version", "-h"], dash), EXIT_OK);
    assert.match(dash.stdout.text, /^usage: diagnos version \[-h\] \[--json\] \[--no-color\]$/m);
});

test("version --json: the wrapper, its runtime, and no Python layers when none is on PATH", async () => {
    const io = fakeIo();
    assert.equal(await main(["version", "--json"], io), EXIT_OK);
    const info = JSON.parse(io.stdout.text) as Record<string, unknown>;
    assert.deepEqual(Object.keys(info), ["diagnos", "node", "implementation", "executable", "platform", "extras", "layers"]);
    assert.equal(info.diagnos, VERSION);
    assert.deepEqual(info.extras, {});
    assert.equal(info.layers, null);
    const text = fakeIo();
    assert.equal(await main(["version"], text), EXIT_OK);
    assert.match(text.stdout.text, /none on PATH yet/);
});

test("version reads the Python layers from the Python diagnos on PATH", { skip: !POSIX }, async () => {
    const folder = temp();
    const python = pythonDiagnos(path.join(folder, "bin"), { sdk: true, cli: false, api: false, "dev-certs": false }, path.join(folder, "log"));
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["version", "--json"], io), EXIT_OK);
    const info = JSON.parse(io.stdout.text) as { extras: unknown; layers: unknown };
    assert.deepEqual(info.extras, { sdk: true, cli: false, api: false, "dev-certs": false });
    assert.deepEqual(info.layers, { command: python, diagnos: "0.1.0", python: "3.12.3" });
    const text = fakeIo({ env: io.env });
    assert.equal(await main(["version"], text), EXIT_OK);
    assert.match(text.stdout.text, /cli +not installed · não instalado +diagnos setup cli/);
    assert.match(text.stdout.text, /dev-certs +not installed · não instalado +pip install "diagnos\[dev-certs\]==0\.1\.0"/);
});

test("a full-CLI command without the CLI answers with how to install it, exit 69", async () => {
    const io = fakeIo();
    assert.equal(await main(["login"], io), EXIT_UNAVAILABLE);
    assert.match(io.stderr.text, /`diagnos login` is part of the full command line/);
    assert.match(io.stderr.text, /diagnos setup cli/);
});

test("with the CLI installed, any other command is handed over unchanged, exit code included", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "log");
    pythonDiagnos(path.join(folder, "bin"), { sdk: false, cli: true, api: false }, log, 7);
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["--no-color", "patients", "list", "--json"], io), 7);
    assert.deepEqual(logged(log), ["--no-color", "patients", "list", "--json", `marker=${VERSION}`]);
});

test("only the Python base's own shape counts; a wrapper that answers is skipped", { skip: !POSIX }, async () => {
    const folder = temp();
    const shim = path.join(folder, "shim");
    program(shim, "diagnos", `echo '{"diagnos":"0.1.0","node":"22.0.0","extras":{},"layers":null}'`);
    const python = pythonDiagnos(path.join(folder, "real"), { cli: true }, path.join(folder, "log"));
    const found = await layers(fakeIo({ env: { PATH: searchPath(shim, path.join(folder, "real")) } }));
    assert.equal(found?.command, python);
    assert.equal(await layers(fakeIo({ env: { PATH: searchPath(path.join(folder, "real")), [MARKER]: "1" } })), null);
    assert.equal(reported('{"diagnos":"0.1.0","python":"3.12","extras":{"cli":"yes"}}', "x"), null);
    assert.equal(reported("not json", "x"), null);
    assert.equal(reported("[]", "x"), null);
});

test("a link to this very package is never taken for the Python diagnos", { skip: !POSIX }, () => {
    const root = fileURLToPath(new URL("..", import.meta.url));
    const folder = temp();
    const link = path.join(folder, "diagnos");
    symlinkSync(path.join(root, "src", "cli.ts"), link);
    assert.equal(ours(link, root), true);
    assert.equal(ours(program(path.join(folder, "other"), "diagnos", "exit 0"), root), false);
});

test("the executable runs, prints, and sets the exit code", () => {
    const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url));
    const output = execFileSync(process.execPath, [cli, "docs", "dev"], { encoding: "utf8", env: { PATH: "" } });
    assert.equal(output, "https://dev.diagnos.health\n");
    assert.throws(
        () => execFileSync(process.execPath, [cli, "docs", "nope"], { stdio: "pipe", env: { PATH: "" } }),
        (error: { status?: number }) => error.status === EXIT_USAGE,
    );
});
