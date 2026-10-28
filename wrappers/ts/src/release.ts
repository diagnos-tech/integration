/**
 * 🇺🇸 This wrapper's version, and the diagnos release it sets up: the same number, in PyPI's spelling.
 *
 * The npm package is versioned with the Python package and its images, so `diagnos@0.1.0` from npm sets up
 * `diagnos==0.1.0` from PyPI and `ghcr.io/diagnos-tech/diagnos-api:0.1.0`. npm spells a release candidate
 * `0.2.0-rc.1`; PyPI and the image tags spell it `0.2.0rc1`. Any other version is a development build: it pins
 * nothing and pulls no image.
 *
 * 🇧🇷 A versão deste wrapper, e o release do diagnos que ele configura: o mesmo número, na grafia do PyPI.
 *
 * O pacote npm é versionado junto com o pacote Python e as imagens dele, então o `diagnos@0.1.0` do npm configura
 * o `diagnos==0.1.0` do PyPI e a `ghcr.io/diagnos-tech/diagnos-api:0.1.0`. O npm escreve um release candidate como
 * `0.2.0-rc.1`; o PyPI e as tags de imagem, como `0.2.0rc1`. Qualquer outra versão é um build de desenvolvimento:
 * não fixa nada e não baixa imagem.
 *
 * @module
 */

import { readFileSync } from "node:fs";

/** 🇺🇸 The Python distribution every layer belongs to. 🇧🇷 A distribuição Python de que toda camada faz parte. */
export const DISTRIBUTION = "diagnos";

/** 🇺🇸 A release as PyPI spells it (the Python base's `_version.RELEASE`). 🇧🇷 Um release na grafia do PyPI (o `_version.RELEASE` da base Python). */
export const RELEASE = /^[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?$/;

const NPM_RELEASE = /^([0-9]+\.[0-9]+\.[0-9]+)(?:-(a|b|rc)\.([0-9]+))?$/;
const MANIFEST = new URL("../package.json", import.meta.url);

/** 🇺🇸 This package's version, from its own `package.json`. 🇧🇷 A versão deste pacote, do próprio `package.json`. */
export const VERSION: string = (JSON.parse(readFileSync(MANIFEST, "utf8")) as { version: string }).version;

/**
 * 🇺🇸 The PyPI release matching npm `version` (`0.2.0-rc.1` → `0.2.0rc1`), or `null` for a development build.
 *
 * 🇧🇷 O release do PyPI que corresponde à `version` do npm (`0.2.0-rc.1` → `0.2.0rc1`), ou `null` num build de dev.
 */
export function pythonRelease(version: string = VERSION): string | null {
    const match = NPM_RELEASE.exec(version);
    if (match === null) {
        return null;
    }
    const [, base, stage, number] = match;
    return stage === undefined ? (base ?? null) : `${base}${stage}${number}`;
}

/**
 * 🇺🇸 `diagnos[extra]==<release>`: one layer at exactly this wrapper's release (unpinned on a development build).
 *
 * 🇧🇷 `diagnos[extra]==<release>`: uma camada exatamente no release deste wrapper (sem fixar num build de dev).
 */
export function requirement(extra: string, release: string | null = pythonRelease()): string {
    return release === null ? `${DISTRIBUTION}[${extra}]` : `${DISTRIBUTION}[${extra}]==${release}`;
}
