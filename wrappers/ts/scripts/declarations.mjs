#!/usr/bin/env node
// 🇺🇸 After `tsc`: relative imports in `dist/**/*.d.ts` end in `.js`, like the JavaScript next to them.
//    `rewriteRelativeImportExtensions` rewrites `./io.ts` to `./io.js` in the emitted JavaScript only; a
//    declaration file that keeps `./io.ts` is read correctly by TypeScript 5.7 and later, but not by every
//    consumer's toolchain.
// 🇧🇷 Depois do `tsc`: imports relativos em `dist/**/*.d.ts` terminam em `.js`, como o JavaScript ao lado.
//    O `rewriteRelativeImportExtensions` reescreve `./io.ts` para `./io.js` só no JavaScript emitido; um arquivo
//    de declaração que mantém `./io.ts` é lido certo pelo TypeScript 5.7 em diante, mas não por toda ferramenta
//    de quem consome o pacote.

import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIST = fileURLToPath(new URL("../dist/", import.meta.url));
const RELATIVE_TS = /((?:from\s+|import\()["']\.{1,2}\/[^"']*?)\.ts(["'])/g;

for (const entry of readdirSync(DIST, { recursive: true })) {
    if (!entry.endsWith(".d.ts")) {
        continue;
    }
    const file = path.join(DIST, entry);
    const text = readFileSync(file, "utf8");
    const fixed = text.replace(RELATIVE_TS, "$1.js$2");
    if (fixed !== text) {
        writeFileSync(file, fixed);
    }
}
