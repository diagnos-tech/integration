#!/usr/bin/env node
/**
 * 🇺🇸 The `diagnos` executable: runs one command line and sets the exit code — never `process.exit` on the way
 * out, so every line written reaches a pipe before the process ends.
 *
 * 🇧🇷 O executável `diagnos`: roda uma linha de comando e define o código de saída — nunca `process.exit` na saída,
 * para toda linha escrita chegar a um pipe antes de o processo acabar.
 *
 * @module
 */

import { main } from "./app.ts";
import { EXIT_FAILED } from "./exit-codes.ts";
import { printable } from "./output.ts";

// 🇺🇸 `diagnos docs | head -1`: the reader left, so there is nothing more to say. 🇧🇷 `diagnos docs | head -1`: o leitor saiu, então não há mais o que dizer.
process.stdout.on("error", (error: NodeJS.ErrnoException) => {
    if (error.code !== "EPIPE") {
        throw error;
    }
    process.exit(process.exitCode ?? 0);
});

try {
    process.exitCode = await main(process.argv.slice(2));
} catch (error) {
    process.stderr.write(`diagnos: ${printable(error instanceof Error ? error.message : String(error))}\n`);
    process.exitCode = EXIT_FAILED;
}
