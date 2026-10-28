/**
 * 🇺🇸 `diagnos setup sdk | cli | api` — one layer installed for you, step by step, or exactly told how.
 *
 * Each target checks what it needs (`uv` for the Python layers, Docker for the API), builds a plan, shows every
 * command, asks once and runs it. A missing tool ends with its official install page and exit code
 * `EXIT_UNAVAILABLE`, never with an attempt to install it. `--dry-run` only prints the plan; `--yes` runs it
 * without asking (for scripts and CI).
 *
 * 🇧🇷 `diagnos setup sdk | cli | api` — uma camada instalada para você, passo a passo, ou dito exatamente como.
 *
 * Cada alvo confere o que precisa (`uv` para as camadas Python, Docker para a API), monta um plano, mostra todo
 * comando, pergunta uma vez e roda. Uma ferramenta ausente termina com a página oficial de instalação dela e o
 * código de saída `EXIT_UNAVAILABLE`, nunca com uma tentativa de instalá-la. `--dry-run` só imprime o plano;
 * `--yes` roda sem perguntar (para scripts e CI).
 *
 * @module
 */

import type { Io } from "../io.ts";
import type { Output } from "../output.ts";
import { api } from "./api.ts";
import { cli, sdk } from "./python.ts";
import type { Plan } from "./run.ts";
import { carryOut } from "./run.ts";

/** 🇺🇸 What `diagnos setup` installs, one layer each. 🇧🇷 O que o `diagnos setup` instala, uma camada cada. */
export const TARGETS = {
    sdk: "The Python SDK, in your project (uv) · O SDK Python, no seu projeto (uv)",
    cli: "The full command line (uv) · A linha de comando completa (uv)",
    api: "The REST API's signed container image (Docker) · A imagem assinada da API REST (Docker)",
} as const;

/** 🇺🇸 One `setup` target. 🇧🇷 Um alvo do `setup`. */
export type Target = keyof typeof TARGETS;

/** 🇺🇸 How one `setup` runs. 🇧🇷 Como um `setup` roda. */
export interface SetupOptions {
    readonly assumeYes: boolean;
    readonly dryRun: boolean;
    readonly out: Output;
    readonly io: Io;
}

/**
 * 🇺🇸 Plans `target` and carries it out; resolves to the exit code (`exit-codes`).
 *
 * 🇧🇷 Planeja o `target` e o executa; resolve no código de saída (`exit-codes`).
 */
export async function setup(target: Target, options: SetupOptions): Promise<number> {
    const { out, io } = options;
    const planners: Record<Target, () => Plan | number | Promise<Plan | number>> = {
        sdk: () => sdk(out, io),
        cli: () => cli(out, io),
        api: () => api(out, io),
    };
    const plan = await planners[target]();
    if (typeof plan === "number") {
        return plan;
    }
    return carryOut(plan, out, { assumeYes: options.assumeYes, dryRun: options.dryRun, stdin: io.stdin });
}
