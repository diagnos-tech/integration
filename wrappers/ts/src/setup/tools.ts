/**
 * 🇺🇸 The programs `setup` relies on — `uv`, Docker, cosign — found on `PATH`, never fetched or installed by us.
 *
 * `find` walks `PATH` itself: any relative entry (`.`) would let a planted `uv` in a downloaded folder run as if it
 * were the real one, so only absolute entries count, and on Windows only `.exe` files — a `.bat`/`.cmd` would go
 * through `cmd.exe`, which re-parses its arguments. A missing program is reported with its official install page;
 * `setup` never downloads an installer or pipes one into a shell on anyone's behalf.
 *
 * 🇧🇷 Os programas de que o `setup` depende — `uv`, Docker, cosign — achados no `PATH`, nunca baixados nem instalados.
 *
 * O `find` percorre o `PATH` ele mesmo: qualquer entrada relativa (`.`) deixaria um `uv` plantado numa pasta baixada
 * rodar como se fosse o de verdade, então só entradas absolutas contam, e no Windows só arquivos `.exe` — um
 * `.bat`/`.cmd` passaria pelo `cmd.exe`, que reinterpreta os argumentos. Um programa ausente é relatado com a página
 * oficial de instalação; o `setup` nunca baixa um instalador nem o joga num shell em nome de ninguém.
 *
 * @module
 */

import { execFile } from "node:child_process";
import { accessSync, constants, statSync } from "node:fs";
import path from "node:path";

import type { Output } from "../output.ts";
import { printable } from "../output.ts";

/** 🇺🇸 Where each program's official installer lives. 🇧🇷 Onde mora o instalador oficial de cada programa. */
export const INSTALL_PAGES = {
    uv: "https://docs.astral.sh/uv/getting-started/installation/",
    docker: "https://docs.docker.com/get-started/get-docker/",
    cosign: "https://docs.sigstore.dev/cosign/system_config/installation/",
} as const;

/** 🇺🇸 A program `setup` may need. 🇧🇷 Um programa de que o `setup` pode precisar. */
export type Tool = keyof typeof INSTALL_PAGES;

/** 🇺🇸 What a program printed, and whether it exited `0`. 🇧🇷 O que um programa imprimiu, e se saiu com `0`. */
export interface Captured {
    readonly ok: boolean;
    readonly stdout: string;
}

const DAEMON_TIMEOUT_MS = 20_000;
const WINDOWS_ABSOLUTE = /^(?:[A-Za-z]:[\\/]|[\\/]{2})/;

function searchPath(env: NodeJS.ProcessEnv, platform: string): string {
    if (env.PATH !== undefined || platform !== "win32") {
        return env.PATH ?? "";
    }
    const key = Object.keys(env).find((name) => name.toUpperCase() === "PATH");
    return key === undefined ? "" : (env[key] ?? "");
}

function executable(candidate: string): boolean {
    try {
        accessSync(candidate, constants.X_OK);
        return statSync(candidate).isFile();
    } catch {
        return false;
    }
}

/**
 * 🇺🇸 Every executable `name` on `PATH`, in order, skipping relative entries (and, on Windows, anything but `.exe`).
 *
 * 🇧🇷 Todo executável `name` no `PATH`, em ordem, pulando entradas relativas (e, no Windows, o que não for `.exe`).
 */
export function* candidates(name: string, env: NodeJS.ProcessEnv, platform: string = process.platform): Generator<string> {
    const windows = platform === "win32";
    const paths = windows ? path.win32 : path.posix;
    const filename = windows ? `${name}.exe` : name;
    for (const entry of searchPath(env, platform).split(paths.delimiter)) {
        const absolute = windows ? WINDOWS_ABSOLUTE.test(entry) : paths.isAbsolute(entry);
        if (entry && absolute) {
            const candidate = paths.join(entry, filename);
            if (executable(candidate)) {
                yield candidate;
            }
        }
    }
}

/** 🇺🇸 The absolute path of the first executable `name` on `PATH`, or `null`. 🇧🇷 O caminho absoluto do primeiro executável `name` no `PATH`, ou `null`. */
export function find(name: string, env: NodeJS.ProcessEnv, platform: string = process.platform): string | null {
    for (const candidate of candidates(name, env, platform)) {
        return candidate;
    }
    return null;
}

/**
 * 🇺🇸 Runs `argv` (no shell) and collects its `stdout`; a program that cannot start counts as failed.
 *
 * 🇧🇷 Roda o `argv` (sem shell) e recolhe o `stdout`; um programa que não consegue iniciar conta como falha.
 */
export function capture(argv: readonly string[], env: NodeJS.ProcessEnv, timeout = 0): Promise<Captured> {
    const [program, ...args] = argv;
    return new Promise((resolve) => {
        execFile(
            program ?? "",
            args,
            { env, timeout, windowsHide: true, maxBuffer: 4 * 1024 * 1024, encoding: "utf8" },
            (error, stdout) => resolve({ ok: error === null, stdout }),
        );
    });
}

/** 🇺🇸 Whether the Docker daemon answers — an installed `docker` with a stopped engine cannot pull. 🇧🇷 Se o daemon do Docker responde — um `docker` instalado com o motor parado não consegue baixar. */
export async function dockerRunning(docker: string, env: NodeJS.ProcessEnv): Promise<boolean> {
    const answer = await capture([docker, "info", "--format", "{{.ServerVersion}}"], env, DAEMON_TIMEOUT_MS);
    return answer.ok && answer.stdout.trim() !== "";
}

/** 🇺🇸 One line saying which `name` will run. 🇧🇷 Uma linha dizendo qual `name` vai rodar. */
export function found(out: Output, name: Tool, location: string): void {
    out.line(`${out.style(name, "green")} found · encontrado: ${printable(location)}`);
}

/** 🇺🇸 Says `name` is missing, where to get it, and (`otherwise`) how to go on without it. 🇧🇷 Diz que `name` falta, onde obtê-lo, e (`otherwise`) como seguir sem ele. */
export function missing(out: Output, name: Tool, otherwise?: string): void {
    out.error(`${out.style(name, "red")} not found · não encontrado.`);
    out.error(`  Install it, then run this again · Instale e rode isto de novo: ${INSTALL_PAGES[name]}`);
    if (otherwise !== undefined) {
        out.error(`  Or, without ${name} · Ou, sem ${name}: ${otherwise}`);
    }
}
