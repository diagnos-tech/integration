/**
 * 🇺🇸 What a command touches outside itself — the three streams, the environment and the folder — in one place,
 * so the tests can hand each command their own.
 *
 * 🇧🇷 O que um comando toca fora de si — os três streams, o ambiente e a pasta — num lugar só, para os testes
 * entregarem os seus a cada comando.
 *
 * @module
 */

import type { Readable } from "node:stream";

/** 🇺🇸 Where text goes: `process.stdout`, or a test's buffer. 🇧🇷 Para onde vai o texto: `process.stdout`, ou o buffer de um teste. */
export interface Sink {
    write(text: string): unknown;
    readonly isTTY?: boolean;
}

/** 🇺🇸 The world one run of `diagnos` sees. 🇧🇷 O mundo que uma execução do `diagnos` vê. */
export interface Io {
    readonly stdout: Sink;
    readonly stderr: Sink;
    readonly stdin: Readable & { readonly isTTY?: boolean };
    readonly env: NodeJS.ProcessEnv;
    readonly cwd: string;
}

/** 🇺🇸 This process's own streams, environment and folder. 🇧🇷 Os streams, o ambiente e a pasta deste processo. */
export function processIo(): Io {
    return {
        stdout: process.stdout,
        stderr: process.stderr,
        stdin: process.stdin,
        env: process.env,
        cwd: process.cwd(),
    };
}
