"""The repository's own tooling: the checks behind `make lint` and the docs pipeline behind `make docs`.

This is a package (not a loose folder) so that `python -m scripts.docs.check` and mypy resolve `scripts.docs.*`
the same way; the standalone scripts here (`check_docs.py`, `check_file_size.py`, ...) still run as plain files.
"""
