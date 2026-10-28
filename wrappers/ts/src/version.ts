/**
 * 🇺🇸 `diagnos version` — this installation at a glance: the wrapper, its runtime and platform, and which Python
 * layers are in.
 *
 * The first thing to paste into a bug report. `extras` has exactly the shape the Python base prints, read from the
 * Python `diagnos` on `PATH` (empty when there is none); `layers` says which one answered.
 *
 * 🇧🇷 `diagnos version` — esta instalação de relance: o wrapper, o runtime e a plataforma dele, e quais camadas
 * Python estão dentro.
 *
 * A primeira coisa a colar num relato de bug. `extras` tem exatamente o formato que a base Python imprime, lido do
 * `diagnos` Python no `PATH` (vazio quando não há nenhum); `layers` diz qual respondeu.
 *
 * @module
 */

import { machine } from "node:os";

import { EXIT_OK } from "./exit-codes.ts";
import type { Io } from "./io.ts";
import { layers } from "./layers.ts";
import type { Output } from "./output.ts";
import { printable, table } from "./output.ts";
import { DISTRIBUTION, RELEASE, VERSION } from "./release.ts";
import { TARGETS } from "./setup/index.ts";

/** 🇺🇸 What `diagnos version --json` prints. 🇧🇷 O que o `diagnos version --json` imprime. */
export interface Installation {
    readonly diagnos: string;
    readonly node: string;
    readonly implementation: string;
    readonly executable: string;
    readonly platform: string;
    readonly extras: Readonly<Record<string, boolean>>;
    readonly layers: { readonly command: string; readonly diagnos: string; readonly python: string } | null;
}

function implementation(): string {
    if (process.versions.bun !== undefined) {
        return "Bun";
    }
    return process.versions.deno === undefined ? "Node.js" : "Deno";
}

function hint(extra: string, python: string): string {
    if (extra in TARGETS) {
        return `diagnos setup ${extra}`;
    }
    const pin = RELEASE.test(python) ? `==${python}` : "";
    return `pip install "${DISTRIBUTION}[${extra}]${pin}"`;
}

/** 🇺🇸 What `diagnos version --json` prints, asking the Python base on `PATH` for its extras. 🇧🇷 O que o `diagnos version --json` imprime, perguntando os extras à base Python no `PATH`. */
export async function installation(io: Io): Promise<Installation> {
    const base = await layers(io);
    return {
        diagnos: VERSION,
        node: process.versions.node,
        implementation: implementation(),
        executable: process.execPath,
        platform: `${process.platform}-${machine().toLowerCase()}`,
        extras: base?.extras ?? {},
        layers: base === null ? null : { command: base.command, diagnos: base.diagnos, python: base.python },
    };
}

/**
 * 🇺🇸 Prints the installation, as text or JSON; always succeeds.
 *
 * 🇧🇷 Imprime a instalação, como texto ou JSON; sempre dá certo.
 */
export async function version(out: Output, io: Io): Promise<number> {
    const info = await installation(io);
    if (out.json) {
        out.data(info);
        return EXIT_OK;
    }
    out.line(out.style(`diagnos ${info.diagnos}`, "bold"));
    out.line(`  node      ${info.node} (${info.implementation}) · ${printable(info.executable)}`);
    out.line(`  platform  ${info.platform}`);
    out.line();
    out.line(out.style("Python layers · Camadas Python", "bold"));
    const base = info.layers;
    if (base === null) {
        out.line(out.style("  none on PATH yet · nenhuma no PATH ainda: diagnos setup sdk | cli | api", "dim"));
        return EXIT_OK;
    }
    const python = printable(base.python);
    out.line(`  diagnos ${printable(base.diagnos)} (Python ${python}) · ${printable(base.command)}`);
    const entries = Object.entries(info.extras);
    const rows = entries.map(([extra, present]) =>
        present
            ? [printable(extra), "installed · instalado", ""]
            : [printable(extra), "not installed · não instalado", hint(printable(extra), base.diagnos)],
    );
    table(rows).forEach((row, index) => {
        out.line(entries[index]?.[1] === true ? row : out.style(row, "dim"));
    });
    return EXIT_OK;
}
