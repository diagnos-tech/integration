/**
 * 🇺🇸 Plans and how they run: every step shown first, confirmed once, then run in order until one fails.
 *
 * Nothing here builds a shell command line. A step's argv starts with an absolute path resolved once
 * (`tools.find`), so a later change to `PATH` — or a file named `uv` in the current folder — cannot swap the
 * program between what was shown and what runs. The confirmation is skipped only by an explicit `--yes`; without
 * a terminal to ask on, nothing runs.
 *
 * 🇧🇷 Planos e como rodam: todo passo mostrado antes, confirmado uma vez, e rodado em ordem até um falhar.
 *
 * Nada aqui monta uma linha de comando de shell. O argv de um passo começa com um caminho absoluto resolvido uma vez
 * (`tools.find`), então uma mudança posterior no `PATH` — ou um arquivo chamado `uv` na pasta atual — não troca o
 * programa entre o que foi mostrado e o que roda. A confirmação só é pulada por um `--yes` explícito; sem terminal
 * para perguntar, nada roda.
 *
 * @module
 */

import { spawn } from "node:child_process";
import path from "node:path";
import { createInterface } from "node:readline";
import type { Readable } from "node:stream";

import { EXIT_FAILED, EXIT_OK, EXIT_USAGE } from "../exit-codes.ts";
import type { Output } from "../output.ts";
import { printable } from "../output.ts";

/** 🇺🇸 One thing `setup` does: what it is for, the command a person would type, and how to do it. 🇧🇷 Uma coisa que o `setup` faz: para que serve, o comando que uma pessoa digitaria, e como fazer. */
export interface Step {
    readonly summary: string;
    readonly shown: string;
    readonly action: (out: Output) => Promise<number>;
}

/** 🇺🇸 A target's steps, plus the lines that tell what to do once they all succeed. 🇧🇷 Os passos de um alvo, mais as linhas que dizem o que fazer quando todos dão certo. */
export interface Plan {
    readonly title: string;
    readonly steps: readonly Step[];
    readonly after: readonly string[];
}

// 🇺🇸 `shlex.quote`'s safe set: anything else is single-quoted. 🇧🇷 O conjunto seguro do `shlex.quote`: o resto vai entre aspas simples.
const SHELL_SAFE = /^[\w@%+=:,./-]+$/;
const ANSWERS_YES: ReadonlySet<string> = new Set(["y", "yes", "s", "sim"]);

function posixQuote(word: string): string {
    if (word === "") {
        return "''";
    }
    return SHELL_SAFE.test(word) ? word : `'${word.replaceAll("'", `'"'"'`)}'`;
}

// 🇺🇸 Python's `subprocess.list2cmdline`: the quoting the Microsoft C runtime parses back. 🇧🇷 O `subprocess.list2cmdline` do Python: as aspas que o runtime C da Microsoft lê de volta.
function windowsQuote(word: string): string {
    const quoted = word === "" || word.includes(" ") || word.includes("\t");
    let result = quoted ? '"' : "";
    let backslashes = 0;
    for (const char of word) {
        if (char === "\\") {
            backslashes += 1;
            continue;
        }
        result += char === '"' ? `${"\\".repeat(backslashes * 2)}\\"` : `${"\\".repeat(backslashes)}${char}`;
        backslashes = 0;
    }
    result += "\\".repeat(quoted ? backslashes * 2 : backslashes);
    return quoted ? `${result}"` : result;
}

/**
 * 🇺🇸 `argv` as a person would type it: the program by its bare name, the rest quoted for their shell.
 *
 * Control characters come out escaped (`printable`): a folder name must not be able to rewrite the command shown
 * for approval.
 *
 * 🇧🇷 `argv` como uma pessoa digitaria: o programa pelo nome, o resto entre aspas para o shell dela.
 *
 * Caracteres de controle saem escapados (`printable`): um nome de pasta não pode reescrever o comando mostrado
 * para aprovação.
 */
export function shown(argv: readonly string[], platform: string = process.platform): string {
    const windows = platform === "win32";
    const program = (windows ? path.win32 : path.posix).parse(argv[0] ?? "").name;
    const words = [program, ...argv.slice(1)];
    return printable(words.map(windows ? windowsQuote : posixQuote).join(" "));
}

/**
 * 🇺🇸 Runs `argv` (no shell) with this terminal's input and output; resolves to its exit code (`127` if it cannot
 * start). `quiet` discards its `stdout`.
 *
 * 🇧🇷 Roda o `argv` (sem shell) com a entrada e a saída deste terminal; resolve no código de saída (`127` se não
 * consegue iniciar). `quiet` descarta o `stdout` dele.
 */
export function execute(argv: readonly string[], env: NodeJS.ProcessEnv, quiet = false): Promise<number> {
    const [program, ...args] = argv;
    return new Promise((resolve) => {
        const child = spawn(program ?? "", args, { env, stdio: quiet ? ["inherit", "ignore", "inherit"] : "inherit" });
        child.once("error", () => resolve(127));
        child.once("close", (code) => resolve(code ?? EXIT_FAILED));
    });
}

/** 🇺🇸 A step that runs `argv` and returns its exit code. 🇧🇷 Um passo que roda o `argv` e devolve o código de saída. */
export function command(summary: string, argv: readonly string[], env: NodeJS.ProcessEnv): Step {
    const frozen = Object.freeze([...argv]);
    return { summary, shown: shown(frozen), action: () => execute(frozen, env) };
}

/** 🇺🇸 Prints the plan: numbered steps, each with the command it runs. 🇧🇷 Imprime o plano: passos numerados, cada um com o comando que roda. */
export function show(plan: Plan, out: Output): void {
    out.line(out.style(plan.title, "bold"));
    plan.steps.forEach((step, index) => {
        out.line(`  ${index + 1}. ${step.summary}`);
        out.line(out.style(`     $ ${step.shown}`, "cyan"));
    });
}

/**
 * 🇺🇸 Asks once and defaults to no: only `y`/`yes` or `s`/`sim` agree — Enter alone runs nothing.
 *
 * 🇧🇷 Pergunta uma vez e o padrão é não: só `y`/`yes` ou `s`/`sim` concordam — Enter sozinho não roda nada.
 */
export async function confirm(out: Output, stdin: Readable): Promise<boolean> {
    out.stdout.write("Run it? · Executar? [y/N] ");
    const lines = createInterface({ input: stdin, terminal: false });
    try {
        for await (const line of lines) {
            return ANSWERS_YES.has(line.trim().toLowerCase());
        }
        return false;
    } finally {
        lines.close();
    }
}

/**
 * 🇺🇸 Shows `plan`, asks (unless `--yes`), runs it; `EXIT_FAILED` at the first step that fails.
 *
 * The failed program's own exit code is printed, not returned: `uv` or `docker` exiting `2` must not read as this
 * command's usage error.
 *
 * 🇧🇷 Mostra o `plan`, pergunta (salvo `--yes`), roda; `EXIT_FAILED` no primeiro passo que falhar.
 *
 * O código de saída do programa que falhou é impresso, não devolvido: `uv` ou `docker` saindo com `2` não pode
 * parecer erro de uso deste comando.
 */
export async function carryOut(
    plan: Plan,
    out: Output,
    options: { readonly assumeYes: boolean; readonly dryRun: boolean; readonly stdin: Readable & { readonly isTTY?: boolean } },
): Promise<number> {
    show(plan, out);
    if (options.dryRun) {
        return EXIT_OK;
    }
    if (!options.assumeYes) {
        if (options.stdin.isTTY !== true) {
            out.error("Nothing ran: no terminal to confirm on. Add --yes · Nada rodou: sem terminal. Use --yes");
            return EXIT_USAGE;
        }
        if (!(await confirm(out, options.stdin))) {
            out.line("Nothing ran · Nada rodou.");
            return EXIT_FAILED;
        }
    }
    for (const [index, step] of plan.steps.entries()) {
        const number = index + 1;
        out.line(out.style(`[${number}/${plan.steps.length}] ${step.summary}`, "bold"));
        const code = await step.action(out);
        if (code !== EXIT_OK) {
            out.error(out.style(`Step ${number} failed (exit ${code}) · O passo ${number} falhou (saída ${code})`, "red"));
            return EXIT_FAILED;
        }
    }
    out.line(out.style("Done · Pronto.", "green"));
    if (plan.after.length > 0) {
        out.line();
        out.line(out.style("Next · Próximo:", "bold"));
        for (const line of plan.after) {
            out.line(`  ${line}`);
        }
    }
    return EXIT_OK;
}
