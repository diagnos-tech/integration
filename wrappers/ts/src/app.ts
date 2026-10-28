/**
 * 🇺🇸 The command line: `diagnos docs | version | setup | help` — the contract every diagnos wrapper implements
 * (`wrappers/contract.json`).
 *
 * Any other command — `diagnos login`, `diagnos patients …` — belongs to the full command line, which is Python.
 * When it is installed, the command is handed to it unchanged, with this terminal, and its exit code comes back
 * as is; otherwise the answer is the one line that installs it and exit code `EXIT_UNAVAILABLE`. `--json` and
 * `--no-color` may come before or after the command, as in the full CLI.
 *
 * 🇧🇷 A linha de comando: `diagnos docs | version | setup | help` — o contrato que todo wrapper do diagnos
 * implementa (`wrappers/contract.json`).
 *
 * Qualquer outro comando — `diagnos login`, `diagnos patients …` — pertence à linha de comando completa, que é
 * Python. Quando ela está instalada, o comando lhe é entregue intacto, com este terminal, e o código de saída volta
 * como veio; senão, a resposta é a linha que a instala e o código de saída `EXIT_UNAVAILABLE`. `--json` e
 * `--no-color` podem vir antes ou depois do comando, como na CLI completa.
 *
 * @module
 */

import type { CommandSpec, Flag } from "./args.ts";
import { help, parse, usage } from "./args.ts";
import type { Topic } from "./docs.ts";
import { docs, TOPICS } from "./docs.ts";
import { EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE } from "./exit-codes.ts";
import type { Io } from "./io.ts";
import { processIo } from "./io.ts";
import { forward, layers } from "./layers.ts";
import { Output, printable, table } from "./output.ts";
import { requirement, VERSION } from "./release.ts";
import type { Target } from "./setup/index.ts";
import { setup, TARGETS } from "./setup/index.ts";
import { version } from "./version.ts";

/** 🇺🇸 The four base commands. 🇧🇷 Os quatro comandos da base. */
export type Command = "docs" | "version" | "setup" | "help";

const JSON_FLAG: Flag = { names: ["--json"], key: "json", help: "Machine output · Saída para máquina" };
const NO_COLOR: Flag = { names: ["--no-color"], key: "noColor", help: "Disable ANSI colors · Desliga cores ANSI" };
const GLOBAL_FLAGS: readonly string[] = ["--json", "--no-color"];

/** 🇺🇸 What each command accepts — checked against `wrappers/contract.json` by the tests. 🇧🇷 O que cada comando aceita — conferido com o `wrappers/contract.json` pelos testes. */
export const COMMANDS: Readonly<Record<Command, CommandSpec>> = {
    docs: {
        about: "Help Center, Developer Central and Trust Center links · Links da Central de Ajuda, Developer Central e Trust Center",
        positional: { name: "topic", choices: TOPICS, help: "Print only this URL · Imprime só esta URL" },
        flags: [{ names: ["--open"], key: "open", help: "Open it in the browser · Abre no navegador" }, JSON_FLAG, NO_COLOR],
    },
    version: {
        about: "This installation: version, Node.js, Python layers · Esta instalação: versão, Node.js, camadas Python",
        flags: [JSON_FLAG, NO_COLOR],
    },
    setup: {
        about: "Install the SDK, the CLI or the API, step by step · Instala o SDK, a CLI ou a API, passo a passo",
        positional: { name: "target", choices: Object.keys(TARGETS), help: "What to install · O que instalar" },
        flags: [
            { names: ["--yes", "-y"], key: "yes", help: "Run without asking · Roda sem perguntar" },
            { names: ["--dry-run"], key: "dryRun", help: "Only print the plan · Só imprime o plano" },
            NO_COLOR,
        ],
    },
    help: {
        about: "This help, or a command's · Esta ajuda, ou a de um comando",
        positional: { name: "command", choices: ["docs", "version", "setup", "help"], help: "A command · Um comando" },
        flags: [NO_COLOR],
    },
};

function isCommand(name: string): name is Command {
    return Object.hasOwn(COMMANDS, name);
}

/**
 * 🇺🇸 `argv` with the global flags typed before the command moved after it, where its parser reads them.
 *
 * 🇧🇷 `argv` com as flags globais digitadas antes do comando movidas para depois dele, onde o parser as lê.
 */
export function hoisted(argv: readonly string[]): string[] {
    const first = argv.findIndex((arg) => !GLOBAL_FLAGS.includes(arg));
    if (first === -1) {
        return [...argv];
    }
    return [argv[first] ?? "", ...argv.slice(0, first), ...argv.slice(first + 1)];
}

function overview(out: Output): number {
    const tagline = "the diagnos vault, set up from Node.js · o cofre diagnos, configurado pelo Node.js";
    out.line(`${out.style(`diagnos ${VERSION}`, "bold")} — ${tagline}`);
    out.line();
    out.line("Usage · Uso: diagnos <command> [options]");
    out.line();
    out.line(out.style("Commands · Comandos", "bold"));
    for (const row of table(Object.entries(COMMANDS).map(([name, spec]) => [name, spec.about]))) {
        out.line(row);
    }
    out.line();
    out.line(out.style("Install more · Instale mais", "bold"));
    for (const row of table(Object.entries(TARGETS).map(([target, about]) => [`diagnos setup ${target}`, about]))) {
        out.line(row);
    }
    out.line();
    out.line("diagnos help <command> · the command's options · as opções do comando");
    out.line("Every other command runs the full CLI once installed · Todo outro comando roda a CLI completa, se instalada");
    return EXIT_OK;
}

function commandHelp(out: Output, name: Command): void {
    for (const line of help(`diagnos ${name}`, COMMANDS[name])) {
        out.line(line);
    }
}

async function unknown(name: string, argv: readonly string[], io: Io): Promise<number> {
    const out = Output.terminal(io);
    if (name.startsWith("-")) {
        out.error(`Unknown option · Opção desconhecida: ${printable(name)}  (diagnos help)`);
        return EXIT_USAGE;
    }
    const base = await layers(io);
    if (base?.extras.cli === true) {
        return forward(base.command, argv, io);
    }
    out.error(`\`diagnos ${printable(name)}\` is part of the full command line · faz parte da linha de comando completa.`);
    out.error(`  diagnos setup cli  (or · ou: pipx install "${requirement("cli")}")`);
    return EXIT_UNAVAILABLE;
}

/**
 * 🇺🇸 Runs one command line and resolves to its exit code; never calls `process.exit` itself.
 *
 * 🇧🇷 Roda uma linha de comando e resolve no código de saída; nunca chama `process.exit` ela mesma.
 */
export async function main(argv: readonly string[], io: Io = processIo()): Promise<number> {
    const args = hoisted(argv);
    const name = args[0];
    if (name === undefined || name === "-h" || name === "--help" || GLOBAL_FLAGS.includes(name)) {
        return overview(Output.terminal(io, { noColor: args.includes("--no-color") }));
    }
    if (name === "--version") {
        Output.terminal(io).line(`diagnos ${VERSION}`);
        return EXIT_OK;
    }
    if (!isCommand(name)) {
        return unknown(name, argv, io);
    }
    const spec = COMMANDS[name];
    const parsed = parse(spec, args.slice(1));
    if (parsed.kind === "help") {
        commandHelp(Output.terminal(io), name);
        return EXIT_OK;
    }
    if (parsed.kind === "error") {
        io.stderr.write(`${usage(`diagnos ${name}`, spec)}\ndiagnos ${name}: error: ${parsed.message}\n`);
        return EXIT_USAGE;
    }
    const out = Output.terminal(io, { json: parsed.flags.has("json"), noColor: parsed.flags.has("noColor") });
    switch (name) {
        case "docs":
            return docs(parsed.positional as Topic | undefined, { open: parsed.flags.has("open"), out, io });
        case "version":
            return version(out, io);
        case "setup":
            if (parsed.positional === undefined) {
                commandHelp(out, name);
                return EXIT_USAGE;
            }
            return setup(parsed.positional as Target, { assumeYes: parsed.flags.has("yes"), dryRun: parsed.flags.has("dryRun"), out, io });
        case "help":
            if (parsed.positional === undefined || parsed.positional === "help") {
                return overview(out);
            }
            commandHelp(out, parsed.positional as Command);
            return EXIT_OK;
    }
}
