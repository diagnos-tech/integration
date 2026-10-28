/**
 * 🇺🇸 Plans: how commands are shown for approval, the one confirmation, and running steps until one fails.
 *
 * 🇧🇷 Planos: como os comandos são mostrados para aprovação, a confirmação única, e rodar passos até um falhar.
 *
 * @module
 */

import assert from "node:assert/strict";
import { chmodSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { EXIT_FAILED, EXIT_OK, EXIT_USAGE } from "../src/exit-codes.ts";
import { Output } from "../src/output.ts";
import type { Plan } from "../src/setup/run.ts";
import { carryOut, command, confirm, shown } from "../src/setup/run.ts";
import { candidates, find } from "../src/setup/tools.ts";
import { fakeIo, logged, POSIX, program, searchPath, temp } from "./helpers.ts";

function plan(codes: number[], ran: number[]): Plan {
    return {
        title: "Setup · test",
        steps: codes.map((code, index) => ({
            summary: `step ${index + 1}`,
            shown: `tool ${index + 1}`,
            action: async () => {
                ran.push(index + 1);
                return code;
            },
        })),
        after: ["next thing"],
    };
}

test("shown names the program bare and quotes the rest for a POSIX shell", () => {
    assert.equal(
        shown(["/usr/bin/uv", "add", "--project", "/tmp/my dir", "diagnos[sdk]>=0.1.0"], "linux"),
        "uv add --project '/tmp/my dir' 'diagnos[sdk]>=0.1.0'",
    );
    assert.equal(shown(["/usr/bin/uv", "it's", ""], "linux"), `uv 'it'"'"'s' ''`);
});

test("shown escapes control characters, so a folder name cannot rewrite the line", () => {
    assert.equal(shown(["/usr/bin/uv", "init", "/tmp/\x1b[2Kok"], "linux"), "uv init '/tmp/\\x1b[2Kok'");
});

test("shown quotes for the Microsoft C runtime on Windows", () => {
    assert.equal(
        shown(["C:\\tools\\uv.exe", "add", "C:\\My Dir\\", 'a"b', "plain"], "win32"),
        'uv add "C:\\My Dir\\\\" a\\"b plain',
    );
});

test("a dry run shows the plan and runs nothing", async () => {
    const io = fakeIo();
    const ran: number[] = [];
    const code = await carryOut(plan([0], ran), new Output(io.stdout, io.stderr), { assumeYes: false, dryRun: true, stdin: io.stdin });
    assert.equal(code, EXIT_OK);
    assert.deepEqual(ran, []);
    assert.match(io.stdout.text, /1\. step 1\n {5}\$ tool 1/);
});

test("without a terminal and without --yes, nothing runs and the exit code is 2", async () => {
    const io = fakeIo({ input: "y\n", tty: false });
    const ran: number[] = [];
    const code = await carryOut(plan([0], ran), new Output(io.stdout, io.stderr), { assumeYes: false, dryRun: false, stdin: io.stdin });
    assert.equal(code, EXIT_USAGE);
    assert.deepEqual(ran, []);
    assert.match(io.stderr.text, /no terminal to confirm on/);
});

test("the confirmation defaults to no", async () => {
    for (const [answer, agreed] of [["y\n", true], ["SIM\n", true], ["yes\n", true], ["\n", false], ["n\n", false], ["", false]] as const) {
        const io = fakeIo({ input: answer, tty: true });
        assert.equal(await confirm(new Output(io.stdout, io.stderr), io.stdin), agreed, JSON.stringify(answer));
    }
});

test("a declined plan runs nothing and fails", async () => {
    const io = fakeIo({ input: "n\n", tty: true });
    const ran: number[] = [];
    const code = await carryOut(plan([0], ran), new Output(io.stdout, io.stderr), { assumeYes: false, dryRun: false, stdin: io.stdin });
    assert.equal(code, EXIT_FAILED);
    assert.deepEqual(ran, []);
});

test("steps run in order and stop at the first failure, whose own code is printed, not returned", async () => {
    const io = fakeIo();
    const ran: number[] = [];
    const code = await carryOut(plan([0, 2, 0], ran), new Output(io.stdout, io.stderr), { assumeYes: true, dryRun: false, stdin: io.stdin });
    assert.equal(code, EXIT_FAILED);
    assert.deepEqual(ran, [1, 2]);
    assert.match(io.stderr.text, /Step 2 failed \(exit 2\)/);
});

test("a confirmed plan runs every step and tells what comes next", async () => {
    const io = fakeIo({ input: "s\n", tty: true });
    const ran: number[] = [];
    const code = await carryOut(plan([0, 0], ran), new Output(io.stdout, io.stderr), { assumeYes: false, dryRun: false, stdin: io.stdin });
    assert.equal(code, EXIT_OK);
    assert.deepEqual(ran, [1, 2]);
    assert.match(io.stdout.text, /Done · Pronto\.\n\nNext · Próximo:\n {2}next thing\n$/);
});

test("a command step runs its argv without a shell and returns the exit code", { skip: !POSIX }, async () => {
    const folder = temp();
    const log = path.join(folder, "log");
    const tool = program(folder, "tool", `printf '%s\\n' "$@" > '${log}'; exit 3`);
    const step = command("run tool", [tool, "a b", "$HOME", ";rm -rf"], { PATH: searchPath() });
    assert.equal(await step.action(new Output(fakeIo().stdout, fakeIo().stderr)), 3);
    assert.deepEqual(logged(log), ["a b", "$HOME", ";rm -rf"]);
});

test("find skips relative PATH entries and files that are not executable", { skip: !POSIX }, () => {
    const folder = temp();
    const good = path.join(folder, "good");
    const plain = path.join(folder, "plain");
    program(good, "uv", "exit 0");
    program(plain, "uv", "exit 0");
    chmodSync(path.join(plain, "uv"), 0o644);
    const env = { PATH: [".", "relative/bin", plain, good].join(path.delimiter) };
    assert.equal(find("uv", env), path.join(good, "uv"));
    assert.deepEqual([...candidates("uv", { PATH: "." })], []);
    assert.equal(find("uv", {}), null);
});
