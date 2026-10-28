/**
 * 🇺🇸 The exit codes — the same four every diagnos wrapper returns (`wrappers/contract.json`).
 *
 * `EXIT_UNAVAILABLE` borrows `EX_UNAVAILABLE` from BSD `sysexits.h`: something this command needs (`uv`, Docker)
 * is not installed, which a script can tell apart from any failure.
 *
 * 🇧🇷 Os códigos de saída — os mesmos quatro que todo wrapper do diagnos devolve (`wrappers/contract.json`).
 *
 * `EXIT_UNAVAILABLE` empresta o `EX_UNAVAILABLE` do `sysexits.h` do BSD: algo de que este comando precisa (`uv`,
 * Docker) não está instalado, o que um script distingue de qualquer falha.
 *
 * @module
 */

/** 🇺🇸 Success. 🇧🇷 Sucesso. */
export const EXIT_OK = 0;
/** 🇺🇸 A step failed, or the confirmation was declined. 🇧🇷 Um passo falhou, ou a confirmação foi negada. */
export const EXIT_FAILED = 1;
/** 🇺🇸 Usage error, including "no terminal to confirm on". 🇧🇷 Erro de uso, inclusive "sem terminal para confirmar". */
export const EXIT_USAGE = 2;
/** 🇺🇸 Something this needs is not installed. 🇧🇷 Algo de que isto precisa não está instalado. */
export const EXIT_UNAVAILABLE = 69;
