"""🇺🇸 The repository's own tooling: the checks behind `make lint` and the docs pipeline behind `make docs`.

A package (not a loose folder) so `python -m scripts.docs.check` and mypy
resolve `scripts.docs.*` the same way; the standalone scripts here
(`check_docs.py`, `check_bilingual.py`, …) still run as plain files.

🇧🇷 O ferramental do próprio repositório: as checagens do `make lint` e o pipeline de docs do `make docs`.

Um pacote (não uma pasta solta) para `python -m scripts.docs.check` e o mypy
resolverem `scripts.docs.*` do mesmo jeito; os scripts avulsos daqui
(`check_docs.py`, `check_bilingual.py`, …) continuam rodando como arquivos.
"""
