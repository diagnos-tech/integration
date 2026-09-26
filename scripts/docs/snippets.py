"""🇺🇸 Runs every ```` ```python ```` block of the published docs, so no example can rot.

The convention, stated once (`docs/README.md` explains it to writers):

- every block fenced as ```` ```python ```` on a page of `docs/site.json`
  (both languages) runs, top to bottom, in one namespace per page — like a
  notebook, a later block may use `vault` or `patient` from an earlier one;
- ```` ```python no-run ```` opts one block out (a fragment, a signature,
  code that needs a real OpenBao); any other language never runs;
- each page gets a fresh `sandbox` (the real SDK against an in-memory
  vault) and its own temporary working directory; output is captured and
  only shown when a block fails.

A failure is reported at the Markdown line that raised: the block is
compiled with its body shifted to the line it has in the file.

🇧🇷 Roda todo bloco ```` ```python ```` da doc publicada, para nenhum exemplo apodrecer.

A convenção, dita uma vez (`docs/README.pt-BR.md` a explica para quem escreve):

- todo bloco cercado como ```` ```python ```` numa página do `docs/site.json`
  (nas duas línguas) roda, de cima para baixo, num namespace por página —
  como um notebook, um bloco posterior pode usar `vault` ou `patient` de um
  anterior;
- ```` ```python no-run ```` tira um bloco (um fragmento, uma assinatura,
  código que precisa de um OpenBao de verdade); qualquer outra linguagem
  nunca roda;
- cada página ganha um `sandbox` novo (o SDK de verdade contra um cofre em
  memória) e o próprio diretório temporário; a saída é capturada e só
  aparece quando um bloco falha.

Uma falha é reportada na linha do Markdown que lançou: o bloco é compilado
com o corpo deslocado para a linha que ele tem no arquivo.
"""

from __future__ import annotations

import contextlib
import io
import traceback
from dataclasses import dataclass
from pathlib import Path

from .markdown import Fence, fences
from .sandbox import sandbox

RUNNABLE = "python"
SKIP_FLAG = "no-run"


@dataclass(frozen=True)
class Outcome:
    """🇺🇸 How many blocks of one file ran, and the problem lines of the ones that failed.

    🇧🇷 Quantos blocos de um arquivo rodaram, e as linhas de problema dos que falharam.
    """

    ran: int
    problems: list[str]


def runnable(text: str) -> list[Fence]:
    """🇺🇸 The blocks of a page that run. 🇧🇷 Os blocos de uma página que rodam."""
    return [fence for fence in fences(text) if fence.language == RUNNABLE and SKIP_FLAG not in fence.flags]


def _failure(where: str, fence: Fence, error: BaseException, output: str) -> str:
    """🇺🇸 `file:line: Error: message`, pointing at the deepest frame inside the Markdown file.

    🇧🇷 `arquivo:linha: Erro: mensagem`, apontando o quadro mais fundo dentro do arquivo Markdown.
    """
    line = fence.line
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.filename == where and frame.lineno is not None:
            line = frame.lineno
    detail = f"{type(error).__name__}: {error}".strip()
    tail = "\n".join(f"    | {row}" for row in output.strip().splitlines()[-8:])
    return f"{where}:{line}: snippet failed · snippet falhou — {detail}" + (f"\n{tail}" if tail else "")


def run_file(path: Path, root: Path) -> Outcome:
    """🇺🇸 Runs one page's blocks in order, in one sandbox; stops that page at its first failure.

    A later block usually depends on an earlier one, so going on after a
    failure would only report the same root cause again.

    🇧🇷 Roda os blocos de uma página em ordem, num sandbox; para a página na primeira falha.

    Um bloco posterior em geral depende de um anterior, então continuar
    depois de uma falha só reportaria a mesma causa de novo.
    """
    blocks = runnable(path.read_text(encoding="utf-8"))
    if not blocks:
        return Outcome(ran=0, problems=[])
    where = str(path.relative_to(root))
    namespace: dict[str, object] = {"__name__": "__docs__"}
    output = io.StringIO()
    with sandbox(), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        for ran, fence in enumerate(blocks):
            try:
                # 🇺🇸 `dont_inherit`: this module's `from __future__` must not leak into the reader's code.
                # 🇧🇷 `dont_inherit`: o `from __future__` deste módulo não pode vazar para o código de quem lê.
                code = compile("\n" * (fence.line - 1) + fence.body, where, "exec", dont_inherit=True)
                exec(code, namespace)  # noqa: S102 — running the docs' own examples is the point
            except (Exception, SystemExit) as error:
                return Outcome(ran=ran + 1, problems=[_failure(where, fence, error, output.getvalue())])
    return Outcome(ran=len(blocks), problems=[])
