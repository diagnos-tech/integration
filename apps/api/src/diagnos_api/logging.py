"""🇺🇸 Structured logging: one JSON object per line, for the `diagnos_api` and `diagnos` loggers.

A container platform (`apps/api/deploy/k8s`) ships stdout to a log aggregator
line by line; JSON-per-line is what lets that aggregator index level,
logger name and message without a fragile regex over free text. What never
appears in a field here matters as much as the format: a request body can
carry a patient's legal name, a token carries a bearer credential, a
filename can itself be sensitive (`chest_ct_re_biopsy.dcm`) — none of that
is a log's job to hold, so no code in this package ever passes one of those
to `logger.info`/`logger.error` (`CONVENTIONS.md`'s "secrets never
logged", extended here to clinical content generally).

🇧🇷 Logging estruturado: um objeto JSON por linha, para os loggers
`diagnos_api` e `diagnos`.

Uma plataforma de containers (`apps/api/deploy/k8s`) manda o stdout para um
agregador de log linha a linha; JSON por linha é o que permite esse
agregador indexar nível, nome do logger e mensagem sem um regex frágil
sobre texto livre. O que nunca aparece num campo aqui importa tanto quanto
o formato: um corpo de requisição pode carregar o nome legal de um
paciente, um token carrega uma credencial bearer, um nome de arquivo pode
ele mesmo ser sensível (`chest_ct_re_biopsia.dcm`) — nada disso é trabalho
de um log guardar, então nenhum código deste pacote passa um desses para
`logger.info`/`logger.error` (o "segredo nunca logado" do `CONVENTIONS.md`,
estendido aqui a conteúdo clínico em geral).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_STRUCTURED_LOGGERS = ("diagnos_api", "diagnos")


class _JsonLineFormatter(logging.Formatter):
    """🇺🇸 Renders one `logging.LogRecord` as one line of JSON.

    🇧🇷 Renderiza um `logging.LogRecord` como uma linha de JSON.
    """

    def format(self, record: logging.LogRecord) -> str:
        """🇺🇸 `timestamp`/`level`/`logger`/`message`, plus a formatted traceback when there is an exception.

        🇧🇷 `timestamp`/`level`/`logger`/`message`, mais um traceback formatado quando há exceção.
        """
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """🇺🇸 Points `diagnos_api` and `diagnos` at one JSON-line `stdout` handler each; idempotent.

    Called once, from `main.run()`, before `uvicorn.run(..., log_config=None)`
    — passing `log_config=None` is what stops uvicorn from installing its own
    logging configuration on top of this one.

    🇧🇷 Aponta `diagnos_api` e `diagnos` para um handler de `stdout` em JSON
    por linha cada; idempotente.

    Chamada uma vez, de `main.run()`, antes de `uvicorn.run(..., log_config=None)`
    — passar `log_config=None` é o que impede o uvicorn de instalar a própria
    configuração de logging por cima desta.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonLineFormatter())
    for name in _STRUCTURED_LOGGERS:
        target = logging.getLogger(name)
        target.handlers = [handler]
        target.setLevel(level)
        target.propagate = False
