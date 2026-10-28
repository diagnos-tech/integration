/**
 * 🇺🇸 Trusting the API image: which digest Docker pulled, and whether the release workflow signed exactly that.
 *
 * Everything that ends up in an argv here is either a constant or matched against a strict pattern first — the
 * version (`release.RELEASE`), the pulled reference (`IMAGE@sha256:<64 hex>`) — so nothing Docker or the
 * environment says can smuggle an option or a second image into a command. The accepted signer is a single
 * identity: `release.yml` in the integration repository, run by the push of the tag of this exact version, through
 * GitHub's OIDC issuer.
 *
 * 🇧🇷 Confiar na imagem da API: qual digest o Docker baixou, e se o workflow de release assinou exatamente esse.
 *
 * Tudo que acaba num argv aqui é uma constante ou é comparado antes com um padrão estrito — a versão
 * (`release.RELEASE`), a referência baixada (`IMAGE@sha256:<64 hex>`) — então nada que o Docker ou o ambiente digam
 * consegue contrabandear uma opção ou uma segunda imagem para um comando. O assinante aceito é uma identidade só: o
 * `release.yml` do repositório integration, rodado pelo push da tag desta versão exata, pelo emissor OIDC do GitHub.
 *
 * @module
 */

import { capture } from "./tools.ts";

/** 🇺🇸 The REST API's image. 🇧🇷 A imagem da API REST. */
export const IMAGE = "ghcr.io/diagnos-tech/diagnos-api";
/** 🇺🇸 GitHub's OIDC issuer. 🇧🇷 O emissor OIDC do GitHub. */
export const ISSUER = "https://token.actions.githubusercontent.com";
/** 🇺🇸 The workflow that signs every release. 🇧🇷 O workflow que assina todo release. */
export const WORKFLOW = "https://github.com/diagnos-tech/integration/.github/workflows/release.yml";
/** 🇺🇸 Releases run on a tag push only; a manual run at the same tag is not a release. 🇧🇷 Releases rodam só no push de uma tag; uma execução manual na mesma tag não é release. */
export const TRIGGER = "push";
/** 🇺🇸 The image's own user, which owns the certificates when root sets them up. 🇧🇷 O usuário da própria imagem, dono dos certificados quando o root os prepara. */
export const IMAGE_USER = "10001:10001";
/** 🇺🇸 cosign 3.1.3 fixed a verification bypass (GHSA-fx35-mq7g-6g98). 🇧🇷 O cosign 3.1.3 corrigiu um desvio de verificação (GHSA-fx35-mq7g-6g98). */
export const MIN_COSIGN: readonly [number, number, number] = [3, 1, 3];

const PINNED = new RegExp(`^${IMAGE.replaceAll(/[.*+?^${}()|[\]\\/]/g, "\\$&")}@sha256:[0-9a-f]{64}$`);
const COSIGN_VERSION = /^v?(\d+)\.(\d+)\.(\d+)/;

/** 🇺🇸 The only signer accepted: the release workflow, run for tag `v<version>`. 🇧🇷 O único assinante aceito: o workflow de release, rodado para a tag `v<versão>`. */
export function identity(version: string): string {
    return `${WORKFLOW}@refs/tags/v${version}`;
}

/** 🇺🇸 `cosign verify` of `reference`, pinned to the release identity, its trigger and GitHub's issuer. 🇧🇷 `cosign verify` de `reference`, preso à identidade do release, ao gatilho dela e ao emissor do GitHub. */
export function verifyArgv(cosign: string, reference: string, version: string): string[] {
    return [
        cosign,
        "verify",
        "--certificate-identity",
        identity(version),
        "--certificate-oidc-issuer",
        ISSUER,
        "--certificate-github-workflow-trigger",
        TRIGGER,
        reference,
    ];
}

/**
 * 🇺🇸 The `IMAGE@sha256:…` Docker recorded when it pulled `tagged`; `null` unless exactly one is well formed.
 *
 * 🇧🇷 O `IMAGE@sha256:…` que o Docker registrou ao baixar `tagged`; `null` salvo se exatamente um for bem formado.
 */
export async function pulledReference(docker: string, tagged: string, env: NodeJS.ProcessEnv): Promise<string | null> {
    const answer = await capture([docker, "image", "inspect", "--format", "{{json .RepoDigests}}", tagged], env);
    let recorded: unknown;
    try {
        recorded = answer.ok ? JSON.parse(answer.stdout) : [];
    } catch {
        return null;
    }
    if (!Array.isArray(recorded)) {
        return null;
    }
    const pinned = new Set(recorded.filter((entry): entry is string => typeof entry === "string" && PINNED.test(entry)));
    return pinned.size === 1 ? ([...pinned][0] ?? null) : null;
}

/** 🇺🇸 `[major, minor, patch]` of the installed cosign, or `null` when it cannot say. 🇧🇷 `[maior, menor, patch]` do cosign instalado, ou `null` quando ele não consegue dizer. */
export async function cosignVersion(cosign: string, env: NodeJS.ProcessEnv): Promise<[number, number, number] | null> {
    const answer = await capture([cosign, "version", "--json"], env);
    let reported: unknown;
    try {
        reported = answer.ok ? (JSON.parse(answer.stdout) as { gitVersion?: unknown }).gitVersion : undefined;
    } catch {
        return null;
    }
    const match = typeof reported === "string" ? COSIGN_VERSION.exec(reported) : null;
    return match === null ? null : [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** 🇺🇸 Whether `found` is at least `wanted`, part by part. 🇧🇷 Se `found` é pelo menos `wanted`, parte a parte. */
export function atLeast(found: readonly number[], wanted: readonly number[]): boolean {
    for (const [index, part] of wanted.entries()) {
        const have = found[index] ?? 0;
        if (have !== part) {
            return have > part;
        }
    }
    return true;
}

/** 🇺🇸 Whether this process runs as root (never on Windows). 🇧🇷 Se este processo roda como root (nunca no Windows). */
export function superuser(): boolean {
    return process.platform !== "win32" && process.geteuid?.() === 0;
}

/**
 * 🇺🇸 The variable the API image of `version` reads its token from: `DIAGNOS_API_TOKEN` up to 0.1, `DIAGNOS_TOKEN`
 * since 0.2 (the service account token).
 *
 * 🇧🇷 A variável de onde a imagem da API da `version` lê o token: `DIAGNOS_API_TOKEN` até a 0.1, `DIAGNOS_TOKEN` desde
 * a 0.2 (o token de conta de serviço).
 */
export function tokenVariable(version: string): string {
    const [major = 0, minor = 0] = version.split(".").map((part) => Number.parseInt(part, 10));
    return major === 0 && minor < 2 ? "DIAGNOS_API_TOKEN" : "DIAGNOS_TOKEN";
}

/**
 * 🇺🇸 A hardened `docker run` of `reference`, by digest: read-only, no capabilities, loopback only.
 *
 * Memory locking comes from `--ulimit memlock`: under `no-new-privileges` the kernel ignores the image's file
 * capability. `--user` matches the owner of the certificates `dev-certs` writes with mode `0600` — except for root,
 * whose certificates are handed to the image's own user instead, so the container never runs as root.
 *
 * 🇧🇷 Um `docker run` endurecido de `reference`, pelo digest: só leitura, sem capabilities, só loopback.
 *
 * O travamento de memória vem do `--ulimit memlock`: sob `no-new-privileges` o kernel ignora a capability de
 * arquivo da imagem. O `--user` casa com o dono dos certificados que o `dev-certs` grava com modo `0600` — salvo
 * para o root, cujos certificados passam ao usuário da própria imagem, para o container nunca rodar como root.
 */
export function runLines(reference: string, version: string, root = false): string[] {
    const user = root ? `chown -R ${IMAGE_USER} certs && ` : "";
    const flags = root ? "" : ' --user "$(id -u):$(id -g)"';
    return [
        `${user}docker run --rm --read-only --tmpfs /tmp --cap-drop ALL${flags} \\`,
        "  --security-opt no-new-privileges:true --ulimit memlock=-1:-1 -p 127.0.0.1:8443:8443 \\",
        `  -e ${tokenVariable(version)} -e DIAGNOS_API_MTLS_CA_FILE=/certs/ca.pem \\`,
        "  -e DIAGNOS_API_TLS_CERT_FILE=/certs/server.pem -e DIAGNOS_API_TLS_KEY_FILE=/certs/server-key.pem \\",
        `  -v "$PWD/certs:/certs:ro" ${reference}`,
    ];
}
