# Política de Segurança

[English](SECURITY.md) · **Português (Brasil)**

## Reportando uma vulnerabilidade

Por favor, **não** abra uma issue pública para uma vulnerabilidade de segurança, mesmo que seja uma suspeita.
Reporte em privado através do **[GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new)**.

Esse formulário vai só para os mantenedores. Vamos confirmar o recebimento do seu relato, trabalhar com você para
entendê-lo e confirmá-lo, e manter você atualizado enquanto preparamos uma correção. Não temos um programa de
recompensa por bugs (bug bounty) no momento.

Vulnerabilidades no próprio serviço do cofre (`https://vault.diagnos.health`) — diferente destes pacotes cliente —
são reportadas pelo mesmo canal: abra um
[security advisory privado](https://github.com/diagnos-tech/integration/security/advisories/new) aqui em vez de
contatar o cofre separadamente, e os mantenedores encaminham internamente.

## Versões suportadas

| Versão | Suportada |
|---|---|
| última `0.1.x` | ✅ |
| qualquer anterior | ❌ |

O `diagnos` é um pacote só — a base e os extras `sdk`, `cli` e `api` — publicado no PyPI junto com as imagens
`ghcr.io/diagnos-tech/diagnos` e `ghcr.io/diagnos-tech/diagnos-api`, tudo sob uma versão. Só o último release recebe
correções de segurança enquanto o projeto está em `0.x` — ainda não há um branch de suporte de longo prazo.

## Escopo

No escopo:

- **A criptografia do SDK** (`src/diagnos/crypto/`) — derivação de chave, selagem híbrida, cifragem de
  conteúdo, assinatura de requisição, e qualquer lugar onde um formato de fio de `docs/PROTOCOL.md` é implementado.
- **O enclave de memória em Rust** (`apps/sdk/native`) — o código responsável por manter chaves de sessão, DEKs e chaves
  privadas fora do swap, de core dumps e de filhos de `fork()`. Veja [`apps/sdk/native/README.md`](apps/sdk/native/README.pt-BR.md)
  para o modelo de ameaça do enclave: o que ele garante, o que explicitamente não garante (root/`CAP_SYS_PTRACE`,
  código rodando no mesmo processo, a janela de exportação do OpenBao, Windows), e onde ficam os blocos `unsafe`.
- **A base** (`src/diagnos/_wrapper/`, `src/diagnos/_entry.py`) — o `diagnos setup` roda `uv`, Docker e cosign
  por você; qualquer coisa que rode um programa que o usuário não viu, que o rode de um caminho inesperado, ou que
  verifique uma imagem com menos rigor que o documentado abaixo.
- **A CLI** (`src/diagnos/cli/`) — interpretação de argumentos, tratamento de credenciais, qualquer coisa que possa vazar um
  token ou conteúdo decifrado para um log, um arquivo ou o descritor de arquivo errado.
- **A API** (`src/diagnos/api/`), incluindo seu tratamento de mutual TLS — validação de certificado, aplicação de CNs
  permitidos, e os manifestos de deploy sob `apps/api/deploy/` (Docker Compose, Kubernetes, bootstrap do OpenBao e
  configuração de auto-unseal).
- **O pipeline de release e as imagens** — `.github/workflows/`, o `Dockerfile`, e qualquer coisa que permita a um
  build, uma assinatura ou um arquivo publicado diferir do que o código e os lockfiles deste repositório dizem.

Fora do escopo: vulnerabilidades que exigem que um atacante já tenha root, `CAP_SYS_PTRACE`, ou execução de código
no mesmo processo do SDK — o modelo de ameaça do enclave documenta isso como limite aceito, não como bug. Veja
[`apps/sdk/native/README.md`](apps/sdk/native/README.pt-BR.md) antes de reportar algo assim.

## Verificando um release

Todo release é construído e assinado por um único workflow — `.github/workflows/release.yml`, rodado para a tag do
release — sem chave, com o [Sigstore](https://www.sigstore.dev/). **Nunca publicamos com token de API nem chave
guardada**: uma distribuição `diagnos` sem proveniência PEP 740 no PyPI, ou um arquivo ou imagem cuja assinatura não
nomeie exatamente esse workflow nessa tag, não é nossa — por favor, reporte. Você precisa do
[cosign](https://docs.sigstore.dev/cosign/system_config/installation/) 3.1.3 ou mais novo (versões anteriores têm um
desvio de verificação, GHSA-fx35-mq7g-6g98) ou do [GitHub CLI](https://cli.github.com/).

```sh
V=0.1.0
ID="https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v$V"
ISSUER="https://token.actions.githubusercontent.com"

# Os arquivos do release no GitHub: os checksums são assinados, todo arquivo está nos checksums.
gh release download "v$V" --repo diagnos-tech/integration --dir "diagnos-$V" && cd "diagnos-$V"
cosign verify-blob --bundle SHA256SUMS.sigstore.json --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER" SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS     # macOS: shasum -a 256 --check --ignore-missing SHA256SUMS

# Um arquivo — inclusive um wheel baixado do PyPI — sozinho.
cosign verify-blob --bundle "diagnos-$V.tar.gz.sigstore.json" --certificate-identity "$ID" \
  --certificate-oidc-issuer "$ISSUER" "diagnos-$V.tar.gz"
gh attestation verify "diagnos-$V.tar.gz" --repo diagnos-tech/integration --cert-identity "$ID"

# As imagens, pelo digest que você vai rodar.
cosign verify "ghcr.io/diagnos-tech/diagnos-api@sha256:<digest>" --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER"
gh attestation verify "oci://ghcr.io/diagnos-tech/diagnos-api@sha256:<digest>" --repo diagnos-tech/integration --cert-identity "$ID"
```

Sempre fixe a identidade (`--certificate-identity` / `--cert-identity`): o `gh attestation verify --repo` sozinho
aceita uma atestação de qualquer branch do repositório. Para aceitar qualquer release em vez de uma versão, use um
`--certificate-identity-regexp '^https://github\.com/diagnos-tech/integration/\.github/workflows/release\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+$'`
ancorado. O `images.txt` de cada release no GitHub lista os dois digests das imagens, assinado do mesmo jeito; o
`diagnos setup api` faz a checagem da imagem para você e imprime o `docker run` pelo digest verificado. Cada release
também traz a proveniência SLSA como `diagnos-$V.intoto.jsonl`, para checagens sem a API do GitHub
(`gh attestation verify "$FILE" --bundle "diagnos-$V.intoto.jsonl" --repo diagnos-tech/integration --cert-identity "$ID"`),
e um SBOM CycloneDX das dependências Python, `diagnos-$V.cdx.json`, assinado como todo outro arquivo.

## O que incluir em um relato

Para nos ajudar a triar e corrigir o problema rapidamente, inclua o máximo que puder do seguinte:

- A camada e a versão afetadas (`diagnos` e quais extras, uma imagem, o pipeline de release, ou um manifesto de
  deploy) — o `diagnos version --json` as imprime.
- Uma descrição da vulnerabilidade e seu impacto (o que um atacante ganha, e o que precisa para explorá-la).
- Passos para reproduzir, ou uma prova de conceito mínima (código, par requisição/resposta, ou diff de manifesto).
- A versão do Python, o sistema operacional e — para o enclave — se `CAP_IPC_LOCK` / `mlock` funcionaram
  (`memory_status()`), já que algumas proteções do enclave degradam de forma graciosa e isso importa para a
  severidade.
- Qualquer correção ou mitigação sugerida, se você tiver uma.

Você não precisa ter uma correção pronta para reportar algo — uma descrição clara do problema já é suficiente para
começar.
