"""🇺🇸 Where a service account token is kept between runs: the system keyring, else OpenBao — never a text file.

A token is a private key. `diagnos login` stores it in the system keyring
when there is one that encrypts at rest (`keychain.py`), otherwise in
OpenBao when `OPENBAO_ADDR` is configured (`openbao.py`), and refuses
otherwise (`TokenStoreError`). Reading follows the same order. CI and
ephemeral containers still pass it in `DIAGNOS_TOKEN`, which is how a CI
secret arrives; that beats both stores (`transport/token_sources.py`).

🇧🇷 Onde um token de conta de serviço fica entre execuções: o chaveiro do sistema, senão o OpenBao — nunca arquivo.

Um token é uma chave privada. O `diagnos login` o guarda no chaveiro do
sistema quando há um que cifra em repouso (`keychain.py`), senão no OpenBao
quando `OPENBAO_ADDR` está configurado (`openbao.py`), e recusa no resto
(`TokenStoreError`). A leitura segue a mesma ordem. CI e containers efêmeros
ainda passam o token em `DIAGNOS_TOKEN`, que é como um segredo de CI chega;
ele vence os dois (`transport/token_sources.py`).
"""

from __future__ import annotations

from .keychain import SERVICE, Keychain, backend_name, is_secure
from .manage import StoreChoice, forget_token, save_token
from .openbao import OpenBaoTokenStore, location

__all__ = [
    "SERVICE",
    "Keychain",
    "OpenBaoTokenStore",
    "StoreChoice",
    "backend_name",
    "forget_token",
    "is_secure",
    "location",
    "save_token",
]
