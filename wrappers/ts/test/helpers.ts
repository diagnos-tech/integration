/**
 * 🇺🇸 Test doubles: buffers that stand in for the terminal, a fake `Io`, and fake programs on a private `PATH`.
 *
 * 🇧🇷 Dublês de teste: buffers no lugar do terminal, um `Io` falso, e programas falsos num `PATH` particular.
 *
 * @module
 */

import { chmodSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Readable } from "node:stream";

import type { Io } from "../src/io.ts";

/** 🇺🇸 Fake programs are `/bin/sh` scripts. 🇧🇷 Programas falsos são scripts `/bin/sh`. */
export const POSIX = process.platform !== "win32";

/** 🇺🇸 A sink that keeps what was written. 🇧🇷 Um destino que guarda o que foi escrito. */
export interface Recorder {
    readonly isTTY: boolean;
    write(text: string): boolean;
    readonly text: string;
}

/** 🇺🇸 A fresh `Recorder`. 🇧🇷 Um `Recorder` novo. */
export function recorder(isTTY = false): Recorder {
    const chunks: string[] = [];
    return {
        isTTY,
        write(text: string): boolean {
            chunks.push(text);
            return true;
        },
        get text(): string {
            return chunks.join("");
        },
    };
}

/** 🇺🇸 An `Io` whose output can be read back. 🇧🇷 Um `Io` cuja saída pode ser lida de volta. */
export interface FakeIo extends Io {
    readonly stdout: Recorder;
    readonly stderr: Recorder;
}

/** 🇺🇸 An `Io` with recorded output, typed input and a chosen environment. 🇧🇷 Um `Io` com saída gravada, entrada digitada e ambiente escolhido. */
export function fakeIo(options: { env?: NodeJS.ProcessEnv; cwd?: string; input?: string; tty?: boolean } = {}): FakeIo {
    const stdin = Object.assign(Readable.from(options.input === undefined ? [] : [options.input]), {
        isTTY: options.tty ?? false,
    });
    return {
        stdout: recorder(),
        stderr: recorder(),
        stdin,
        env: options.env ?? { PATH: "" },
        cwd: options.cwd ?? tmpdir(),
    };
}

/** 🇺🇸 A new empty folder. 🇧🇷 Uma pasta nova e vazia. */
export function temp(): string {
    return mkdtempSync(path.join(tmpdir(), "diagnos-wrapper-"));
}

/** 🇺🇸 Writes an executable `/bin/sh` script `name` into `folder`. 🇧🇷 Grava um script `/bin/sh` executável `name` em `folder`. */
export function program(folder: string, name: string, script: string): string {
    mkdirSync(folder, { recursive: true });
    const file = path.join(folder, name);
    writeFileSync(file, `#!/bin/sh\n${script}\n`);
    chmodSync(file, 0o755);
    return file;
}

/** 🇺🇸 `PATH` with `folders` first, then the system's own shell tools. 🇧🇷 `PATH` com `folders` primeiro, depois as ferramentas de shell do sistema. */
export function searchPath(...folders: string[]): string {
    return [...folders, "/usr/bin", "/bin"].join(path.delimiter);
}

/** 🇺🇸 The lines a fake program logged, or `[]`. 🇧🇷 As linhas que um programa falso registrou, ou `[]`. */
export function logged(file: string): string[] {
    try {
        return readFileSync(file, "utf8").split("\n").filter((line) => line !== "");
    } catch {
        return [];
    }
}

/** 🇺🇸 A fake Python `diagnos` that answers `version --json` with `extras`, and logs anything else. 🇧🇷 Um `diagnos` Python falso que responde `version --json` com `extras`, e registra o resto. */
export function pythonDiagnos(folder: string, extras: Record<string, boolean>, log: string, exitCode = 0): string {
    const report = JSON.stringify({
        diagnos: "0.1.0",
        python: "3.12.3",
        implementation: "CPython",
        executable: "/opt/python/bin/python3",
        platform: "linux-x86_64",
        extras,
    });
    return program(
        folder,
        "diagnos",
        [
            `if [ "$1" = version ]; then echo '${report}'; exit 0; fi`,
            `{ printf '%s\\n' "$@"; echo "marker=$DIAGNOS_WRAPPER"; } > '${log}'`,
            `exit ${exitCode}`,
        ].join("\n"),
    );
}
