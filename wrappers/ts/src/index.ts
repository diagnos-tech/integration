/**
 * 🇺🇸 `diagnos` as a library: the same command line the executable runs, for tools that embed it.
 *
 * 🇧🇷 O `diagnos` como biblioteca: a mesma linha de comando que o executável roda, para ferramentas que o embutem.
 *
 * @module
 */

export { main } from "./app.ts";
export { EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE } from "./exit-codes.ts";
export type { Io, Sink } from "./io.ts";
export { VERSION } from "./release.ts";
