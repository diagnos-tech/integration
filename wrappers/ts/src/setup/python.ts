/**
 * 🇺🇸 `diagnos setup sdk` and `diagnos setup cli` — the Python layers, installed with `uv`.
 *
 * The two differ in *where* the layer belongs. The SDK is a dependency of the code someone is writing, so it goes
 * into their Python project (`uv add`, which also locks it) — or into the active virtual environment, or a new
 * project created right here. The CLI is a command: when a Python `diagnos` is already on `PATH`, that one adds
 * its own CLI where it lives (it knows whether it is a `uv tool`, a virtual environment or a system Python);
 * otherwise the CLI is installed as a `uv tool`.
 *
 * 🇧🇷 `diagnos setup sdk` e `diagnos setup cli` — as camadas Python, instaladas com `uv`.
 *
 * As duas diferem em *onde* a camada pertence. O SDK é dependência do código que alguém escreve, então vai para o
 * projeto Python dessa pessoa (`uv add`, que também o trava) — ou para o ambiente virtual ativo, ou para um projeto
 * novo criado aqui mesmo. A CLI é um comando: quando já há um `diagnos` Python no `PATH`, ele soma a própria CLI
 * onde mora (ele sabe se é um `uv tool`, um ambiente virtual ou um Python de sistema); senão, a CLI é instalada como
 * `uv tool`.
 *
 * @module
 */

import { readFileSync, statSync } from "node:fs";
import path from "node:path";

import { EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE } from "../exit-codes.ts";
import type { Io } from "../io.ts";
import { layers, marked } from "../layers.ts";
import type { Output } from "../output.ts";
import { printable } from "../output.ts";
import { DISTRIBUTION, pythonRelease, requirement } from "../release.ts";
import type { Plan } from "./run.ts";
import { command } from "./run.ts";
import { find, found, missing } from "./tools.ts";

const PROBE = 'python -c "from diagnos import Diagnos; print(Diagnos)"';
const QUICKSTART = "Quickstart · Início rápido: https://dev.diagnos.health";
/** 🇺🇸 What to type once the CLI is in. 🇧🇷 O que digitar quando a CLI estiver dentro. */
export const CLI_NEXT: readonly string[] = ["diagnos login", "diagnos --help"];

function isFile(candidate: string): boolean {
    try {
        return statSync(candidate).isFile();
    } catch {
        return false;
    }
}

function development(out: Output): number {
    out.error(
        "This is a development build, or the diagnos checkout itself: `uv sync` (or `make sync`) installs every " +
            "extra · Isto é um build de desenvolvimento, ou o próprio checkout do diagnos: o `uv sync` (ou " +
            "`make sync`) instala todo extra.",
    );
    return EXIT_FAILED;
}

function uvOrMissing(out: Output, io: Io, otherwise: string): string | null {
    const uv = find("uv", io.env);
    if (uv === null) {
        missing(out, "uv", otherwise);
        return null;
    }
    found(out, "uv", uv);
    return uv;
}

/** 🇺🇸 The nearest folder from `start` upward with a `pyproject.toml` — where `uv add` would write. 🇧🇷 A pasta mais próxima de `start` para cima com um `pyproject.toml` — onde o `uv add` escreveria. */
export function projectRoot(start: string): string | null {
    let folder = path.resolve(start);
    for (;;) {
        if (isFile(path.join(folder, "pyproject.toml"))) {
            return folder;
        }
        const parent = path.dirname(folder);
        if (parent === folder) {
            return null;
        }
        folder = parent;
    }
}

/** 🇺🇸 `[project].name` of the `pyproject.toml` in `root`, or `null` when unreadable or unnamed. 🇧🇷 O `[project].name` do `pyproject.toml` em `root`, ou `null` quando ilegível ou sem nome. */
export function projectName(root: string): string | null {
    let text: string;
    try {
        text = readFileSync(path.join(root, "pyproject.toml"), "utf8");
    } catch {
        return null;
    }
    let inProject = false;
    for (const line of text.split(/\r?\n/)) {
        if (/^\s*\[/.test(line)) {
            inProject = /^\s*\[\s*project\s*\]\s*(?:#.*)?$/.test(line);
            continue;
        }
        const name = inProject ? /^\s*name\s*=\s*(["'])([^"']*)\1/.exec(line) : null;
        if (name !== null) {
            return name[2] ?? null;
        }
    }
    return null;
}

/** 🇺🇸 The interpreter of the active virtual environment (`VIRTUAL_ENV`), or `null`. 🇧🇷 O interpretador do ambiente virtual ativo (`VIRTUAL_ENV`), ou `null`. */
export function virtualPython(env: NodeJS.ProcessEnv, platform: string = process.platform): string | null {
    const root = env.VIRTUAL_ENV;
    const paths = platform === "win32" ? path.win32 : path.posix;
    if (root === undefined || !paths.isAbsolute(root)) {
        return null;
    }
    const interpreter = platform === "win32" ? paths.join(root, "Scripts", "python.exe") : paths.join(root, "bin", "python");
    return isFile(interpreter) ? interpreter : null;
}

/**
 * 🇺🇸 The plan that puts the SDK where the Python code is, or the exit code when there is nothing to run.
 *
 * 🇧🇷 O plano que põe o SDK onde está o código Python, ou o código de saída quando não há o que rodar.
 */
export function sdk(out: Output, io: Io): Plan | number {
    const release = pythonRelease();
    const project = projectRoot(io.cwd);
    if ((project !== null && projectName(project) === DISTRIBUTION) || (project === null && release === null)) {
        return development(out);
    }
    const uv = uvOrMissing(out, io, `python -m pip install "${requirement("sdk", release)}"`);
    if (uv === null) {
        return EXIT_UNAVAILABLE;
    }
    const title = "Setup · sdk — the Python SDK · o SDK Python";
    const floor = release === null ? `${DISTRIBUTION}[sdk]` : `${DISTRIBUTION}[sdk]>=${release}`;
    if (project !== null) {
        const manifest = printable(path.join(project, "pyproject.toml"));
        const add = command(`Add the SDK to ${manifest} · Soma o SDK ao ${manifest}`, [uv, "add", "--project", project, floor], io.env);
        return { title, steps: [add], after: [`uv run ${PROBE}`, QUICKSTART] };
    }
    const interpreter = virtualPython(io.env);
    if (interpreter !== null) {
        const install = [uv, "pip", "install", "--python", interpreter, requirement("sdk", release)];
        const summary = "Add the SDK to the active virtual environment · Soma o SDK ao ambiente virtual ativo";
        return { title, steps: [command(summary, install, io.env)], after: [PROBE, QUICKSTART] };
    }
    const here = printable(io.cwd);
    const steps = [
        command(`Create a Python project in ${here} · Cria um projeto Python em ${here}`, [uv, "init", "--bare", "--no-workspace", io.cwd], io.env),
        command("Add the SDK to it · Soma o SDK a ele", [uv, "add", "--project", io.cwd, floor], io.env),
    ];
    return { title, steps, after: [`uv run ${PROBE}`, QUICKSTART] };
}

/**
 * 🇺🇸 The plan that gives `diagnos` every command, or the exit code when there is nothing to run.
 *
 * 🇧🇷 O plano que dá ao `diagnos` todo comando, ou o código de saída quando não há o que rodar.
 */
export async function cli(out: Output, io: Io): Promise<Plan | number> {
    const base = await layers(io);
    if (base?.extras.cli === true) {
        out.line("The full command line is already installed · A linha de comando completa já está instalada.");
        out.line(`  ${CLI_NEXT[1]}`);
        return EXIT_OK;
    }
    const release = pythonRelease();
    if (release === null) {
        return development(out);
    }
    const title = "Setup · cli — the full command line · a linha de comando completa";
    if (base !== null) {
        const where = printable(base.command);
        const summary = `Let the Python diagnos add its CLI where it lives · Deixa o diagnos Python somar a CLI onde mora (${where})`;
        return { title, steps: [command(summary, [base.command, "setup", "cli", "--yes"], marked(io.env))], after: CLI_NEXT };
    }
    const uv = uvOrMissing(out, io, `pipx install "${requirement("cli", release)}"`);
    if (uv === null) {
        return EXIT_UNAVAILABLE;
    }
    const install = command("Install the CLI as a uv tool · Instala a CLI como ferramenta do uv", [uv, "tool", "install", requirement("cli", release)], io.env);
    return { title, steps: [install], after: CLI_NEXT };
}
