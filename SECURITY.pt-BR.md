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

`diagnos`, `diagnos-cli` e `diagnos-api` são versionados e lançados juntos; "última `0.1.x`" significa a tag mais
recente publicada entre os três. Só o último release recebe correções de segurança enquanto o projeto está em
`0.x` — ainda não há um branch de suporte de longo prazo.

## Escopo

No escopo:

- **A criptografia do SDK** (`sdk/src/diagnos/crypto/`) — derivação de chave, selagem híbrida, cifragem de
  conteúdo, assinatura de requisição, e qualquer lugar onde um formato de fio de `docs/PROTOCOL.md` é implementado.
- **O enclave de memória em Rust** (`sdk/native`) — o código responsável por manter chaves de sessão, DEKs e chaves
  privadas fora do swap, de core dumps e de filhos de `fork()`. Veja [`sdk/native/README.md`](sdk/native/README.pt-BR.md)
  para o modelo de ameaça do enclave: o que ele garante, o que explicitamente não garante (root/`CAP_SYS_PTRACE`,
  código rodando no mesmo processo, a janela de exportação do OpenBao, Windows), e onde ficam os blocos `unsafe`.
- **A CLI** (`cli/`) — interpretação de argumentos, tratamento de credenciais, qualquer coisa que possa vazar um
  token ou conteúdo decifrado para um log, um arquivo ou o descritor de arquivo errado.
- **A API** (`api/`), incluindo seu tratamento de mutual TLS — validação de certificado, aplicação de CNs
  permitidos, e os manifestos de deploy sob `api/deploy/` (Docker Compose, Kubernetes, bootstrap do OpenBao e
  configuração de auto-unseal).

Fora do escopo: vulnerabilidades que exigem que um atacante já tenha root, `CAP_SYS_PTRACE`, ou execução de código
no mesmo processo do SDK — o modelo de ameaça do enclave documenta isso como limite aceito, não como bug. Veja
[`sdk/native/README.md`](sdk/native/README.pt-BR.md) antes de reportar algo assim.

## O que incluir em um relato

Para nos ajudar a triar e corrigir o problema rapidamente, inclua o máximo que puder do seguinte:

- O(s) pacote(s) e versão(ões) afetados (`diagnos`, `diagnos-cli`, `diagnos-api`, ou um manifesto de deploy).
- Uma descrição da vulnerabilidade e seu impacto (o que um atacante ganha, e o que precisa para explorá-la).
- Passos para reproduzir, ou uma prova de conceito mínima (código, par requisição/resposta, ou diff de manifesto).
- A versão do Python, o sistema operacional e — para o enclave — se `CAP_IPC_LOCK` / `mlock` funcionaram
  (`memory_status()`), já que algumas proteções do enclave degradam de forma graciosa e isso importa para a
  severidade.
- Qualquer correção ou mitigação sugerida, se você tiver uma.

Você não precisa ter uma correção pronta para reportar algo — uma descrição clara do problema já é suficiente para
começar.
