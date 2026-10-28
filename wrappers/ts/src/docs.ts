/**
 * 🇺🇸 `diagnos docs` — where to read more: the Help Center, Developer Central and the Trust Center.
 *
 * The bare command lists all three. With a topic it prints that one URL alone, so it composes
 * (`open "$(npx diagnos docs dev)"`); `--open` hands it to the browser instead, through the system's own opener —
 * never a shell.
 *
 * 🇧🇷 `diagnos docs` — onde ler mais: a Central de Ajuda, a Developer Central e o Trust Center.
 *
 * O comando sozinho lista os três. Com um tópico imprime só aquela URL, para compor
 * (`open "$(npx diagnos docs dev)"`); `--open` a entrega ao navegador, pelo abridor do próprio sistema — nunca um
 * shell.
 *
 * @module
 */

import { spawn } from "node:child_process";

import { EXIT_OK, EXIT_USAGE } from "./exit-codes.ts";
import type { Io } from "./io.ts";
import type { Output } from "./output.ts";
import { table } from "./output.ts";
import { find } from "./setup/tools.ts";

/** 🇺🇸 The three documentation sites, by the short name `diagnos docs <topic>` takes. 🇧🇷 Os três sites de documentação, pelo nome curto que o `diagnos docs <tópico>` recebe. */
export const TOPICS = ["help", "dev", "trust"] as const;

/** 🇺🇸 One topic. 🇧🇷 Um tópico. */
export type Topic = (typeof TOPICS)[number];

/** 🇺🇸 One documentation site: its topic, its name, its URL and what is there. 🇧🇷 Um site de documentação: o tópico, o nome, a URL e o que há lá. */
export interface Link {
    readonly topic: Topic;
    readonly name: string;
    readonly url: string;
    readonly about: string;
}

/** 🇺🇸 The three sites, in the contract's order. 🇧🇷 Os três sites, na ordem do contrato. */
export const LINKS: readonly Link[] = [
    {
        topic: "help",
        name: "Help Center",
        url: "https://docs.diagnos.health",
        about: "Guides and answers for every diagnos product · Guias e respostas de todo produto diagnos",
    },
    {
        topic: "dev",
        name: "Developer Central",
        url: "https://dev.diagnos.health",
        about: "SDK, CLI and REST API: guides and reference · SDK, CLI e API REST: guias e referência",
    },
    {
        topic: "trust",
        name: "Trust Center",
        url: "https://trust.diagnos.health",
        about: "Security, privacy and compliance · Segurança, privacidade e conformidade",
    },
];

// 🇺🇸 Each system's own way to open a URL in the default browser. 🇧🇷 O jeito de cada sistema abrir uma URL no navegador padrão.
function opener(platform: string): readonly [string, readonly string[]] {
    if (platform === "darwin") {
        return ["open", []];
    }
    return platform === "win32" ? ["rundll32", ["url.dll,FileProtocolHandler"]] : ["xdg-open", []];
}

/**
 * 🇺🇸 Opens `url` in the default browser; `false` where there is none (no opener, or no display on Linux).
 *
 * 🇧🇷 Abre `url` no navegador padrão; `false` onde não há um (sem abridor, ou sem tela no Linux).
 */
export function openBrowser(url: string, env: NodeJS.ProcessEnv, platform: string = process.platform): Promise<boolean> {
    const graphical = platform === "darwin" || platform === "win32" || Boolean(env.DISPLAY || env.WAYLAND_DISPLAY);
    const [name, args] = opener(platform);
    const program = graphical ? find(name, env, platform) : null;
    if (program === null) {
        return Promise.resolve(false);
    }
    return new Promise((resolve) => {
        const child = spawn(program, [...args, url], { env, detached: true, stdio: "ignore", windowsHide: true });
        child.once("error", () => resolve(false));
        child.once("spawn", () => {
            child.unref();
            resolve(true);
        });
    });
}

/**
 * 🇺🇸 Lists the three sites, prints one URL, or opens it; resolves to the exit code.
 *
 * 🇧🇷 Lista os três sites, imprime uma URL ou a abre; resolve no código de saída.
 */
export async function docs(topic: Topic | undefined, options: { readonly open: boolean; readonly out: Output; readonly io: Io }): Promise<number> {
    const { out } = options;
    const chosen = LINKS.filter((link) => topic === undefined || link.topic === topic);
    const first = chosen[0];
    if (options.open) {
        if (topic === undefined || first === undefined) {
            out.error(`--open needs a topic · --open precisa de um tópico: ${TOPICS.join(", ")}`);
            return EXIT_USAGE;
        }
        if (!(await openBrowser(first.url, options.io.env))) {
            out.error(`No browser here · Sem navegador aqui: ${first.url}`);
        }
        return EXIT_OK;
    }
    if (out.json) {
        out.data(Object.fromEntries(chosen.map((link) => [link.topic, { name: link.name, url: link.url }])));
    } else if (topic !== undefined && first !== undefined) {
        out.line(first.url);
    } else {
        for (const row of table(chosen.map((link) => [link.name, link.url, link.about]), 0)) {
            out.line(row);
        }
    }
    return EXIT_OK;
}
