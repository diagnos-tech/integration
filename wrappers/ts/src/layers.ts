/**
 * 🇺🇸 The Python `diagnos` beside this wrapper: found on `PATH`, asked `diagnos version --json`, never imported.
 *
 * The SDK, the full command line and the API are Python; this wrapper only sets them up. To know which layers are
 * already in, it asks the Python base the way a person would — `diagnos version --json` — and trusts nothing but
 * that answer's shape. The same program receives every command this wrapper does not have (`diagnos login`, …)
 * once its CLI is installed, so one `diagnos` answers everything wherever it comes first on `PATH`.
 *
 * Two guards keep a `diagnos` from finding itself: a candidate inside this package is skipped, and every program
 * started from here carries `DIAGNOS_WRAPPER`, so a package manager's shim that leads back to this wrapper answers
 * without looking any further.
 *
 * 🇧🇷 O `diagnos` Python ao lado deste wrapper: achado no `PATH`, perguntado com `diagnos version --json`, nunca importado.
 *
 * O SDK, a linha de comando completa e a API são Python; este wrapper só os configura. Para saber quais camadas já
 * estão dentro, ele pergunta à base Python como uma pessoa faria — `diagnos version --json` — e só confia no
 * formato dessa resposta. O mesmo programa recebe todo comando que este wrapper não tem (`diagnos login`, …) quando
 * a CLI dele está instalada, então um `diagnos` só responde a tudo, seja qual for o primeiro no `PATH`.
 *
 * Duas guardas impedem um `diagnos` de achar a si mesmo: um candidato dentro deste pacote é pulado, e todo programa
 * iniciado daqui leva `DIAGNOS_WRAPPER`, para um shim de gerenciador de pacotes que leve de volta a este wrapper
 * responder sem procurar mais.
 *
 * @module
 */

import { realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Io } from "./io.ts";
import { VERSION } from "./release.ts";
import { execute } from "./setup/run.ts";
import { candidates, capture } from "./setup/tools.ts";

/** 🇺🇸 Set on every program started from here. 🇧🇷 Definida em todo programa iniciado daqui. */
export const MARKER = "DIAGNOS_WRAPPER";

/** 🇺🇸 What the Python base reports about itself. 🇧🇷 O que a base Python informa sobre si. */
export interface Layers {
    readonly command: string;
    readonly diagnos: string;
    readonly python: string;
    readonly extras: Readonly<Record<string, boolean>>;
}

const PACKAGE_ROOT = fileURLToPath(new URL("..", import.meta.url));
const PROBE_TIMEOUT_MS = 20_000;
const MAX_PROBES = 4;

/** 🇺🇸 `env` for a program started from here: marked, so it never comes back looking for us. 🇧🇷 O `env` de um programa iniciado daqui: marcado, para ele nunca voltar procurando a gente. */
export function marked(env: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
    return { ...env, [MARKER]: VERSION };
}

/** 🇺🇸 Whether `candidate` is this very package (a link to `dist/cli.js`), or cannot be resolved. 🇧🇷 Se `candidate` é este mesmo pacote (um link para `dist/cli.js`), ou não pode ser resolvido. */
export function ours(candidate: string, root: string = PACKAGE_ROOT): boolean {
    try {
        const real = realpathSync(candidate);
        const home = realpathSync(root);
        return real === home || real.startsWith(home.endsWith(path.sep) ? home : `${home}${path.sep}`);
    } catch {
        return true;
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * 🇺🇸 The Python base's `version --json`, if `stdout` is exactly that shape; `null` for anything else.
 *
 * 🇧🇷 O `version --json` da base Python, se `stdout` tem exatamente esse formato; `null` para qualquer outra coisa.
 */
export function reported(stdout: string, command: string): Layers | null {
    let value: unknown;
    try {
        value = JSON.parse(stdout);
    } catch {
        return null;
    }
    if (!isRecord(value)) {
        return null;
    }
    const { diagnos, python, extras } = value;
    if (typeof diagnos !== "string" || typeof python !== "string" || !isRecord(extras)) {
        return null;
    }
    const flags = Object.entries(extras);
    if (!flags.every(([, present]) => typeof present === "boolean")) {
        return null;
    }
    return { command, diagnos, python, extras: Object.fromEntries(flags) as Record<string, boolean> };
}

/**
 * 🇺🇸 The first Python `diagnos` on `PATH` and what it has installed, or `null` when there is none.
 *
 * 🇧🇷 O primeiro `diagnos` Python no `PATH` e o que ele tem instalado, ou `null` quando não há nenhum.
 */
export async function layers(io: Io): Promise<Layers | null> {
    if (io.env[MARKER] !== undefined) {
        return null;
    }
    let probes = 0;
    for (const candidate of candidates("diagnos", io.env)) {
        if (ours(candidate)) {
            continue;
        }
        if (probes === MAX_PROBES) {
            break;
        }
        probes += 1;
        const answer = await capture([candidate, "version", "--json"], { ...marked(io.env), NO_COLOR: "1" }, PROBE_TIMEOUT_MS);
        const found = answer.ok ? reported(answer.stdout, candidate) : null;
        if (found !== null) {
            return found;
        }
    }
    return null;
}

/**
 * 🇺🇸 Hands `argv` to the Python `diagnos` at `command`, with this terminal, and returns its exit code unchanged.
 *
 * 🇧🇷 Entrega o `argv` ao `diagnos` Python em `command`, com este terminal, e devolve o código de saída intacto.
 */
export function forward(command: string, argv: readonly string[], io: Io): Promise<number> {
    return execute([command, ...argv], marked(io.env));
}
