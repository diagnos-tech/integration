/**
 * 🇺🇸 `diagnos setup api` — the REST API as its signed container image, through Docker.
 *
 * Pull the image by this wrapper's release, read the digest Docker recorded, verify *that digest* with cosign, and
 * run it by that digest: what was checked is byte for byte what runs, so a tag moved in between cannot slip past.
 * An image whose signature fails is removed on the spot. Without cosign (or with one older than `MIN_COSIGN`) the
 * pull still happens, the result is announced as NOT verified, and the command that verifies it is printed
 * alongside.
 *
 * 🇧🇷 `diagnos setup api` — a API REST como a imagem de container assinada dela, via Docker.
 *
 * Baixar a imagem pelo release deste wrapper, ler o digest que o Docker registrou, verificar *esse digest* com o
 * cosign, e rodá-la por esse digest: o que foi checado é, byte a byte, o que roda, então uma tag movida no meio do
 * caminho não passa. Uma imagem cuja assinatura falha é removida na hora. Sem cosign (ou com um mais velho que
 * `MIN_COSIGN`) o download acontece mesmo assim, o resultado é anunciado como NÃO verificado, e o comando que o
 * verifica é impresso junto.
 *
 * @module
 */

import { EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE } from "../exit-codes.ts";
import type { Io } from "../io.ts";
import type { Output } from "../output.ts";
import { printable } from "../output.ts";
import { pythonRelease, requirement, VERSION } from "../release.ts";
import {
    atLeast,
    cosignVersion,
    IMAGE,
    MIN_COSIGN,
    pulledReference,
    runLines,
    superuser,
    verifyArgv,
} from "./image.ts";
import type { Plan, Step } from "./run.ts";
import { command, execute, shown } from "./run.ts";
import { capture, dockerRunning, find, found, INSTALL_PAGES, missing } from "./tools.ts";

/** 🇺🇸 Where running the API for real is explained. 🇧🇷 Onde rodar a API de verdade é explicado. */
export const DEPLOY_GUIDE = "https://github.com/diagnos-tech/integration/tree/main/apps/api/deploy";

function pinAndVerify(docker: string, cosign: string | null, tagged: string, version: string, env: NodeJS.ProcessEnv): Step {
    const certificates = `uvx --from "${requirement("dev-certs", version)}" diagnos-api dev-certs certs`;
    const action = async (out: Output): Promise<number> => {
        const reference = await pulledReference(docker, tagged, env);
        if (reference === null) {
            out.error(`Docker reports no single digest for ${tagged} · O Docker não informa um digest único`);
            return EXIT_FAILED;
        }
        if (cosign === null) {
            out.error(`${out.style("NOT verified · NÃO verificada", "yellow")}: ${reference}`);
            out.error(`  ${shown(verifyArgv("cosign", reference, version))}`);
        } else if ((await execute(verifyArgv(cosign, reference, version), env, true)) !== EXIT_OK) {
            await capture([docker, "image", "rm", tagged], env);
            out.error(out.style(`Signature check failed; image removed · Assinatura não confere; removida: ${reference}`, "red"));
            return EXIT_FAILED;
        } else {
            out.line(out.style(`Verified: signed by the v${version} release · Verificada: assinada pelo release`, "green"));
        }
        out.line(`Certificates for a local run · Certificados para rodar local: ${certificates}`);
        out.line("Run it, by digest · Rode, pelo digest:");
        for (const line of runLines(reference, version, superuser())) {
            out.line(`  ${line}`);
        }
        return EXIT_OK;
    };
    return {
        summary: "Pin the pulled digest and verify its signature · Fixa o digest baixado e verifica a assinatura",
        shown: shown(verifyArgv("cosign", `${IMAGE}@<pulled digest>`, version)),
        action,
    };
}

async function trustedCosign(out: Output, env: NodeJS.ProcessEnv): Promise<string | null> {
    const cosign = find("cosign", env);
    if (cosign === null) {
        out.line("cosign not found: the image will not be verified · cosign ausente: sem verificação");
        out.line(`  ${INSTALL_PAGES.cosign}`);
        return null;
    }
    const installed = await cosignVersion(cosign, env);
    if (installed === null || !atLeast(installed, MIN_COSIGN)) {
        const wanted = MIN_COSIGN.join(".");
        out.line(`cosign older than ${wanted}: the image will not be verified · cosign anterior a ${wanted}: sem verificação`);
        return null;
    }
    found(out, "cosign", cosign);
    return cosign;
}

/**
 * 🇺🇸 The plan that pulls and verifies the API image; an exit code when Docker is not ready.
 *
 * 🇧🇷 O plano que baixa e verifica a imagem da API; um código de saída quando o Docker não está pronto.
 */
export async function api(out: Output, io: Io): Promise<Plan | number> {
    const version = pythonRelease();
    if (version === null) {
        out.error(`No published image for a development version · Sem imagem publicada para versão de dev: ${printable(VERSION)}`);
        return EXIT_FAILED;
    }
    const docker = find("docker", io.env);
    if (docker === null) {
        missing(out, "docker", `uv tool install "${requirement("api", version)}"  (diagnos-api, no container · sem container)`);
        return EXIT_UNAVAILABLE;
    }
    if (!(await dockerRunning(docker, io.env))) {
        out.error("Docker is installed but not running · O Docker está instalado, mas parado.");
        out.error("  Start Docker Desktop, or · Abra o Docker Desktop, ou: sudo systemctl start docker");
        return EXIT_UNAVAILABLE;
    }
    found(out, "docker", docker);
    const tagged = `${IMAGE}:${version}`;
    const steps = [
        command(`Pull the API image · Baixa a imagem da API (${tagged})`, [docker, "pull", tagged], io.env),
        pinAndVerify(docker, await trustedCosign(out, io.env), tagged, version, io.env),
    ];
    return { title: "Setup · api — the REST API, as a container · a API REST, como container", steps, after: [DEPLOY_GUIDE] };
}
