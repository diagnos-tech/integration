/**
 * 🇺🇸 The arguments of one base command, read the way the Python base's `argparse` reads them.
 *
 * Each command takes at most one positional with fixed choices and a few boolean flags. `-h`/`--help` anywhere
 * prints the command's help; a wrong choice or an unknown argument is a usage error (exit code `2`) with the same
 * `usage:` and `error:` lines `argparse` prints. Nothing here reads a value from a flag, so no flag can carry text.
 *
 * 🇧🇷 Os argumentos de um comando da base, lidos do jeito que o `argparse` da base Python os lê.
 *
 * Cada comando recebe no máximo um posicional com escolhas fixas e algumas flags booleanas. `-h`/`--help` em
 * qualquer lugar imprime a ajuda do comando; uma escolha errada ou um argumento desconhecido é erro de uso (código
 * de saída `2`) com as mesmas linhas `usage:` e `error:` que o `argparse` imprime. Nada aqui lê valor de flag, então
 * nenhuma flag carrega texto.
 *
 * @module
 */

import { printable, table } from "./output.ts";

/** 🇺🇸 A boolean flag: its spellings, the key it sets, its help. 🇧🇷 Uma flag booleana: as grafias, a chave que define, a ajuda. */
export interface Flag {
    readonly names: readonly string[];
    readonly key: string;
    readonly help: string;
}

/** 🇺🇸 The one positional a command may take. 🇧🇷 O único posicional que um comando pode receber. */
export interface Positional {
    readonly name: string;
    readonly choices: readonly string[];
    readonly help: string;
}

/** 🇺🇸 Everything one command accepts. 🇧🇷 Tudo que um comando aceita. */
export interface CommandSpec {
    readonly about: string;
    readonly positional?: Positional;
    readonly flags: readonly Flag[];
}

/** 🇺🇸 The outcome of reading one command's arguments. 🇧🇷 O resultado de ler os argumentos de um comando. */
export type Parsed =
    | { readonly kind: "options"; readonly positional: string | undefined; readonly flags: ReadonlySet<string> }
    | { readonly kind: "help" }
    | { readonly kind: "error"; readonly message: string };

/**
 * 🇺🇸 Reads `argv` (what follows the command's name) against `spec`.
 *
 * 🇧🇷 Lê o `argv` (o que vem depois do nome do comando) contra a `spec`.
 */
export function parse(spec: CommandSpec, argv: readonly string[]): Parsed {
    const flags = new Set<string>();
    const unknown: string[] = [];
    let positional: string | undefined;
    let literal = false;
    for (const arg of argv) {
        if (!literal && arg === "--") {
            literal = true;
        } else if (!literal && arg.startsWith("-") && arg !== "-") {
            if (arg === "-h" || arg === "--help") {
                return { kind: "help" };
            }
            const flag = spec.flags.find((candidate) => candidate.names.includes(arg));
            if (flag === undefined) {
                unknown.push(arg);
            } else {
                flags.add(flag.key);
            }
        } else if (spec.positional !== undefined && positional === undefined) {
            const { name, choices } = spec.positional;
            if (!choices.includes(arg)) {
                const allowed = choices.map((choice) => `'${choice}'`).join(", ");
                return { kind: "error", message: `argument ${name}: invalid choice: '${printable(arg)}' (choose from ${allowed})` };
            }
            positional = arg;
        } else {
            unknown.push(arg);
        }
    }
    if (unknown.length > 0) {
        return { kind: "error", message: `unrecognized arguments: ${unknown.map(printable).join(" ")}` };
    }
    return { kind: "options", positional, flags };
}

/** 🇺🇸 The `usage:` line of `program`. 🇧🇷 A linha `usage:` de `program`. */
export function usage(program: string, spec: CommandSpec): string {
    const parts = ["[-h]", ...spec.flags.map((flag) => `[${flag.names[0] ?? ""}]`)];
    if (spec.positional !== undefined) {
        parts.push(`[{${spec.positional.choices.join(",")}}]`);
    }
    return `usage: ${program} ${parts.join(" ")}`;
}

/** 🇺🇸 The whole help of `program`, line by line. 🇧🇷 A ajuda inteira de `program`, linha a linha. */
export function help(program: string, spec: CommandSpec): string[] {
    const lines = [usage(program, spec), "", spec.about, ""];
    if (spec.positional !== undefined) {
        lines.push("positional arguments:", ...table([[`{${spec.positional.choices.join(",")}}`, spec.positional.help]]), "");
    }
    const options = [
        ["-h, --help", "Show this help and exit · Mostra esta ajuda e sai"],
        ...spec.flags.map((flag) => [flag.names.join(", "), flag.help]),
    ];
    lines.push("options:", ...table(options));
    return lines;
}
