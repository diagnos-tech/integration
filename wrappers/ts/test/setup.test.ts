/**
 * 🇺🇸 `setup sdk`, `setup cli` and `setup api` against fake `uv`, `docker`, `cosign` and Python `diagnos`.
 *
 * 🇧🇷 `setup sdk`, `setup cli` e `setup api` contra `uv`, `docker`, `cosign` e `diagnos` Python falsos.
 *
 * @module
 */

import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { main } from "../src/app.ts";
import { EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE } from "../src/exit-codes.ts";
import { pythonRelease } from "../src/release.ts";
import { atLeast, IMAGE, identity, runLines, tokenVariable, verifyArgv } from "../src/setup/image.ts";
import { projectName, projectRoot } from "../src/setup/python.ts";
import { fakeIo, logged, POSIX, program, pythonDiagnos, searchPath, temp } from "./helpers.ts";

const RELEASE = pythonRelease() ?? "";
const DIGEST = `${IMAGE}@sha256:${"a".repeat(64)}`;

function fakeUv(folder: string, log: string): string {
    return program(folder, "uv", `printf '%s\\n' "$@" >> '${log}'`);
}

function fakeDocker(folder: string, log: string, digests: string[] = [DIGEST], running = true): string {
    return program(
        folder,
        "docker",
        [
            `echo "$*" >> '${log}'`,
            `case "$1 $2" in`,
            `  "info "*) ${running ? "echo 27.3.1" : "exit 1"} ;;`,
            `  "image inspect") echo '${JSON.stringify(digests)}' ;;`,
            `esac`,
        ].join("\n"),
    );
}

function fakeCosign(folder: string, log: string, version: string, verifies: boolean): string {
    return program(
        folder,
        "cosign",
        [
            `if [ "$1" = version ]; then echo '{"gitVersion":"${version}"}'; exit 0; fi`,
            `printf '%s\\n' "$@" >> '${log}'`,
            `exit ${verifies ? 0 : 1}`,
        ].join("\n"),
    );
}

test("projectRoot walks up to the nearest pyproject.toml; projectName reads [project] only", () => {
    const root = temp();
    writeFileSync(path.join(root, "pyproject.toml"), '[tool.other]\nname = "nope"\n\n[project]\nname = "my-app"\n');
    const deep = path.join(root, "src", "pkg");
    mkdirSync(deep, { recursive: true });
    assert.equal(projectRoot(deep), root);
    assert.equal(projectName(root), "my-app");
    assert.equal(projectName(deep), null);
});

test("setup sdk adds the SDK to the Python project it is in", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "uv.log");
    writeFileSync(path.join(folder, "pyproject.toml"), '[project]\nname = "my-app"\n');
    fakeUv(path.join(folder, "bin"), log);
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) }, cwd: folder });
    assert.equal(await main(["setup", "sdk", "--yes"], io), EXIT_OK);
    assert.deepEqual(logged(log), ["add", "--project", folder, `diagnos[sdk]>=${RELEASE}`]);
    assert.match(io.stdout.text, /uv run python -c "from diagnos import Diagnos; print\(Diagnos\)"/);
});

test("setup sdk outside a project creates one, then adds the SDK", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "uv.log");
    fakeUv(path.join(folder, "bin"), log);
    const work = path.join(folder, "work");
    mkdirSync(work);
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) }, cwd: work });
    assert.equal(await main(["setup", "sdk", "-y"], io), EXIT_OK);
    assert.deepEqual(logged(log), ["init", "--bare", "--no-workspace", work, "add", "--project", work, `diagnos[sdk]>=${RELEASE}`]);
});

test("setup sdk installs into the active virtual environment", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "uv.log");
    fakeUv(path.join(folder, "bin"), log);
    const venv = path.join(folder, "venv");
    const python = program(path.join(venv, "bin"), "python", "exit 0");
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")), VIRTUAL_ENV: venv }, cwd: folder });
    assert.equal(await main(["setup", "sdk", "--yes"], io), EXIT_OK);
    assert.deepEqual(logged(log), ["pip", "install", "--python", python, `diagnos[sdk]==${RELEASE}`]);
});

test("setup sdk leaves the diagnos checkout itself alone", async () => {
    const folder = temp();
    writeFileSync(path.join(folder, "pyproject.toml"), '[project]\nname = "diagnos"\n');
    const io = fakeIo({ cwd: folder });
    assert.equal(await main(["setup", "sdk", "--yes"], io), EXIT_FAILED);
    assert.match(io.stderr.text, /uv sync/);
});

test("without uv, setup says where to get it and exits 69", async () => {
    const io = fakeIo({ cwd: temp() });
    assert.equal(await main(["setup", "cli"], io), EXIT_UNAVAILABLE);
    assert.match(io.stderr.text, /uv not found/);
    assert.match(io.stderr.text, /https:\/\/docs\.astral\.sh\/uv\/getting-started\/installation\//);
    assert.match(io.stderr.text, new RegExp(`pipx install "diagnos\\[cli\\]==${RELEASE.replaceAll(".", "\\.")}"`));
});

test("setup cli installs the CLI as a uv tool, pinned to this release", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "uv.log");
    fakeUv(path.join(folder, "bin"), log);
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["setup", "cli", "--yes"], io), EXIT_OK);
    assert.deepEqual(logged(log), ["tool", "install", `diagnos[cli]==${RELEASE}`]);
    assert.match(io.stdout.text, /diagnos login/);
});

test("setup cli lets an installed Python diagnos add its own CLI", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "diagnos.log");
    const python = pythonDiagnos(path.join(folder, "bin"), { sdk: true, cli: false, api: false }, log);
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["setup", "cli", "--dry-run"], io), EXIT_OK);
    assert.match(io.stdout.text, /\$ diagnos setup cli --yes/);
    assert.ok(io.stdout.text.includes(python));
    assert.deepEqual(logged(log), []);
});

test("setup cli has nothing to do when the CLI is already there", { skip: !POSIX }, async () => {
    const folder = temp();
    pythonDiagnos(path.join(folder, "bin"), { sdk: false, cli: true, api: false }, path.join(folder, "log"));
    const io = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["setup", "cli"], io), EXIT_OK);
    assert.match(io.stdout.text, /already installed/);
});

test("the API's token variable follows the image's version", () => {
    assert.equal(tokenVariable("0.1.0"), "DIAGNOS_API_TOKEN");
    assert.equal(tokenVariable("0.2.0"), "DIAGNOS_TOKEN");
    assert.equal(tokenVariable("0.2.0rc1"), "DIAGNOS_TOKEN");
    assert.equal(tokenVariable("1.0.0"), "DIAGNOS_TOKEN");
});

test("the run lines pin the digest and never run the container as root", () => {
    const user = runLines(DIGEST, "0.1.0");
    assert.match(user[0] ?? "", /--user "\$\(id -u\):\$\(id -g\)"/);
    assert.match(user[2] ?? "", /-e DIAGNOS_API_TOKEN /);
    assert.ok(user[4]?.endsWith(DIGEST));
    const root = runLines(DIGEST, "0.2.0", true);
    assert.match(root[0] ?? "", /^chown -R 10001:10001 certs && docker run/);
    assert.doesNotMatch(root[0] ?? "", /--user/);
});

test("cosign verifies against one identity: release.yml, at this tag, pushed, through GitHub", () => {
    assert.deepEqual(verifyArgv("cosign", DIGEST, "0.1.0"), [
        "cosign",
        "verify",
        "--certificate-identity",
        "https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v0.1.0",
        "--certificate-oidc-issuer",
        "https://token.actions.githubusercontent.com",
        "--certificate-github-workflow-trigger",
        "push",
        DIGEST,
    ]);
    assert.equal(identity("0.2.0rc1").endsWith("@refs/tags/v0.2.0rc1"), true);
    assert.equal(atLeast([3, 1, 3], [3, 1, 3]), true);
    assert.equal(atLeast([3, 2, 0], [3, 1, 3]), true);
    assert.equal(atLeast([3, 1, 2], [3, 1, 3]), false);
    assert.equal(atLeast([2, 9, 9], [3, 1, 3]), false);
});

test("setup api pulls, verifies the pulled digest and prints the run by digest", { skip: !POSIX }, async () => {
    const folder = temp();
    const bin = path.join(folder, "bin");
    const log = path.join(folder, "log");
    fakeDocker(bin, log);
    fakeCosign(bin, log, "v3.2.0", true);
    const io = fakeIo({ env: { PATH: searchPath(bin) } });
    assert.equal(await main(["setup", "api", "--yes"], io), EXIT_OK);
    assert.ok(logged(log).includes(`pull ${IMAGE}:${RELEASE}`));
    assert.ok(logged(log).includes(DIGEST));
    assert.match(io.stdout.text, /Verified: signed by the v/);
    assert.ok(io.stdout.text.includes(`-v "$PWD/certs:/certs:ro" ${DIGEST}`));
});

test("an image whose signature fails is removed and the setup fails", { skip: !POSIX }, async () => {
    const folder = temp();
    const bin = path.join(folder, "bin");
    const log = path.join(folder, "log");
    fakeDocker(bin, log);
    fakeCosign(bin, log, "v3.2.0", false);
    const io = fakeIo({ env: { PATH: searchPath(bin) } });
    assert.equal(await main(["setup", "api", "--yes"], io), EXIT_FAILED);
    assert.ok(logged(log).includes(`image rm ${IMAGE}:${RELEASE}`));
    assert.match(io.stderr.text, /Signature check failed; image removed/);
    assert.doesNotMatch(io.stdout.text, /docker run/);
});

test("without a recent cosign the image is pulled but announced as NOT verified", { skip: !POSIX }, async () => {
    const folder = temp();
    const bin = path.join(folder, "bin");
    const log = path.join(folder, "log");
    fakeDocker(bin, log);
    fakeCosign(bin, log, "v2.4.1", true);
    const io = fakeIo({ env: { PATH: searchPath(bin) } });
    assert.equal(await main(["setup", "api", "--yes"], io), EXIT_OK);
    assert.match(io.stdout.text, /cosign older than 3\.1\.3/);
    assert.match(io.stderr.text, /NOT verified · NÃO verificada/);
    assert.match(io.stderr.text, /cosign verify --certificate-identity/);
});

test("a pull that leaves no single well-formed digest fails before anything is run", { skip: !POSIX }, async () => {
    const folder = temp();
    const bin = path.join(folder, "bin");
    const log = path.join(folder, "log");
    fakeDocker(bin, log, [DIGEST, `${IMAGE}@sha256:${"b".repeat(64)}`, "--evil"]);
    const io = fakeIo({ env: { PATH: searchPath(bin) } });
    assert.equal(await main(["setup", "api", "--yes"], io), EXIT_FAILED);
    assert.match(io.stderr.text, /no single digest/);
});

test("setup api needs Docker installed and running", { skip: !POSIX }, async () => {
    const missingIo = fakeIo();
    assert.equal(await main(["setup", "api"], missingIo), EXIT_UNAVAILABLE);
    assert.match(missingIo.stderr.text, /docker not found/);
    const folder = temp();
    fakeDocker(path.join(folder, "bin"), path.join(folder, "log"), [DIGEST], false);
    const stopped = fakeIo({ env: { PATH: searchPath(path.join(folder, "bin")) } });
    assert.equal(await main(["setup", "api"], stopped), EXIT_UNAVAILABLE);
    assert.match(stopped.stderr.text, /installed but not running/);
});
