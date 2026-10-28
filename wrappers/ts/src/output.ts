/**
 * 🇺🇸 How the wrapper writes: plain lines, color only on a real terminal, JSON for scripts.
 *
 * Color follows the conventions people already set once for every tool: `NO_COLOR` (https://no-color.org), a
 * `dumb` terminal, or output that is not a terminal turn it off. `printable` escapes any text this program did not
 * write before it reaches a terminal.
 *
 * 🇧🇷 Como o wrapper escreve: linhas simples, cor só num terminal de verdade, JSON para scripts.
 *
 * A cor segue as convenções que as pessoas já configuram uma vez para toda ferramenta: `NO_COLOR`
 * (https://no-color.org), um terminal `dumb`, ou uma saída que não é terminal a desligam. O `printable` escapa
 * todo texto que este programa não escreveu antes de ele chegar a um terminal.
 *
 * @module
 */

import type { Io, Sink } from "./io.ts";

const RESET = "\x1b[0m";
const CODES = { bold: "1", dim: "2", red: "31", green: "32", yellow: "33", cyan: "36" } as const;
// 🇺🇸 Python's `str.isprintable`: categories Other (Cc, Cf, Cs, Co, Cn) and Separator (Zl, Zp, Zs), save the space.
// 🇧🇷 O `str.isprintable` do Python: categorias Other (Cc, Cf, Cs, Co, Cn) e Separator (Zl, Zp, Zs), salvo o espaço.
const UNPRINTABLE = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}\p{Zs}]/u;
const NAMED_ESCAPES: Readonly<Record<string, string>> = { "\t": "\\t", "\n": "\\n", "\r": "\\r" };

/** 🇺🇸 A named ANSI style. 🇧🇷 Um estilo ANSI nomeado. */
export type Style = keyof typeof CODES;

/**
 * 🇺🇸 Whether ANSI color belongs on `stream`: a terminal, `NO_COLOR` unset, not `TERM=dumb`, VT-capable.
 *
 * Legacy Windows consoles print escape codes literally; Windows Terminal (`WT_SESSION`) and terminals that set
 * `TERM` (Git Bash, MSYS) render them.
 *
 * 🇧🇷 Se cor ANSI cabe em `stream`: um terminal, `NO_COLOR` não definida, não `TERM=dumb`, com suporte a VT.
 *
 * Consoles legados do Windows imprimem os códigos literalmente; o Windows Terminal (`WT_SESSION`) e terminais que
 * definem `TERM` (Git Bash, MSYS) os renderizam.
 */
export function colorWanted(stream: Sink, env: NodeJS.ProcessEnv, platform: string = process.platform): boolean {
    if (env.NO_COLOR || env.TERM === "dumb" || stream.isTTY !== true) {
        return false;
    }
    return platform !== "win32" || env.WT_SESSION !== undefined || env.TERM !== undefined;
}

/** 🇺🇸 Where and how one command writes: the two streams, JSON or text, color or not. 🇧🇷 Onde e como um comando escreve: os dois streams, JSON ou texto, com cor ou sem. */
export class Output {
    readonly stdout: Sink;
    readonly stderr: Sink;
    readonly json: boolean;
    readonly color: boolean;

    constructor(stdout: Sink, stderr: Sink, options: { readonly json?: boolean; readonly color?: boolean } = {}) {
        this.stdout = stdout;
        this.stderr = stderr;
        this.json = options.json ?? false;
        this.color = options.color ?? false;
    }

    /** 🇺🇸 The run's own streams, colored when `stdout` is a capable terminal. 🇧🇷 Os streams da execução, coloridos quando o `stdout` é um terminal capaz. */
    static terminal(io: Io, options: { readonly json?: boolean; readonly noColor?: boolean } = {}): Output {
        const color = options.noColor !== true && colorWanted(io.stdout, io.env);
        return new Output(io.stdout, io.stderr, { json: options.json ?? false, color });
    }

    /** 🇺🇸 One line on `stdout`. 🇧🇷 Uma linha no `stdout`. */
    line(text = ""): void {
        this.stdout.write(`${text}\n`);
    }

    /** 🇺🇸 One line on `stderr`. 🇧🇷 Uma linha no `stderr`. */
    error(text: string): void {
        this.stderr.write(`${text}\n`);
    }

    /** 🇺🇸 `value` as indented JSON on `stdout` — the whole output of a `--json` run. 🇧🇷 `value` como JSON indentado no `stdout` — a saída inteira de uma execução `--json`. */
    data(value: unknown): void {
        this.line(JSON.stringify(value, null, 2));
    }

    /** 🇺🇸 `text` wrapped in the named ANSI styles, or unchanged without color. 🇧🇷 `text` envolvido nos estilos ANSI nomeados, ou intacto sem cor. */
    style(text: string, ...styles: readonly Style[]): string {
        if (!this.color || styles.length === 0) {
            return text;
        }
        return `\x1b[${styles.map((name) => CODES[name]).join(";")}m${text}${RESET}`;
    }
}

/**
 * 🇺🇸 `text` with every character a terminal would act on written as its escape (`\x1b`, `\n`, `‮`).
 *
 * For text this program did not write — a folder name, a `PATH` entry: an escape sequence or a bidirectional
 * override in it could otherwise recolor, hide or reorder the very line a person is asked to approve. The escapes
 * are Python's `unicode_escape`, so both wrappers print the same bytes.
 *
 * 🇧🇷 `text` com todo caractere que um terminal interpretaria escrito como escape (`\x1b`, `\n`, `‮`).
 *
 * Para texto que este programa não escreveu — um nome de pasta, uma entrada do `PATH`: uma sequência de escape ou
 * um override bidirecional nele poderia recolorir, esconder ou reordenar a própria linha que alguém deve aprovar.
 * Os escapes são os do `unicode_escape` do Python, para os dois wrappers imprimirem os mesmos bytes.
 */
export function printable(text: string): string {
    let result = "";
    for (const char of text) {
        result += char !== " " && UNPRINTABLE.test(char) ? escaped(char) : char;
    }
    return result;
}

function escaped(char: string): string {
    const named = NAMED_ESCAPES[char];
    if (named !== undefined) {
        return named;
    }
    const point = char.codePointAt(0) ?? 0;
    const hex = point.toString(16);
    if (point < 0x100) {
        return `\\x${hex.padStart(2, "0")}`;
    }
    return point < 0x10000 ? `\\u${hex.padStart(4, "0")}` : `\\U${hex.padStart(8, "0")}`;
}

/** 🇺🇸 `rows` as aligned columns (the last one left ragged), one string per row. 🇧🇷 `rows` como colunas alinhadas (a última solta), uma string por linha. */
export function table(rows: readonly (readonly string[])[], indent = 2): string[] {
    const first = rows[0];
    if (first === undefined) {
        return [];
    }
    const width = (cell: string): number => [...cell].length;
    const columns = first.length - 1;
    const widths = Array.from({ length: columns }, (_, column) =>
        Math.max(...rows.map((row) => width(row[column] ?? ""))),
    );
    const pad = " ".repeat(indent);
    return rows.map((row) => {
        const cells = widths.map((size, column) => {
            const cell = row[column] ?? "";
            return cell + " ".repeat(size - width(cell));
        });
        return (pad + [...cells, row[columns] ?? ""].join("  ")).trimEnd();
    });
}
