"""The R2 half of the double: presigned URLs, SSE-C validation, and the plain-bytes object store.

`_StorageMixin` only ever sees the same shapes the real R2 gives `VaultTransport` — a `PUT` locked to
the size a URL was signed for, a `GET` gated on the same SSE-C key an object was written with. It has
no idea whether the object behind a URL is a document version, a draft, or a drive node; that mapping
lives in `_documents.py`/`_nodes.py`, which only ever call `self._object_url` to name one.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any

import httpx

_SSE_C_ALGORITHM_HEADER = "x-amz-server-side-encryption-customer-algorithm"
_SSE_C_CLIENT_HEADERS = ["x-amz-server-side-encryption-customer-key", "x-amz-server-side-encryption-customer-key-md5"]

_INVALID_SSE_C = object()


def _sse_c_key_of(request: httpx.Request) -> object:
    """The request's SSE-C key (`None` without one); `_INVALID_SSE_C` when the trio is incomplete or wrong."""
    algorithm = request.headers.get("x-amz-server-side-encryption-customer-algorithm")
    key = request.headers.get("x-amz-server-side-encryption-customer-key")
    md5 = request.headers.get("x-amz-server-side-encryption-customer-key-md5")
    if algorithm is None and key is None and md5 is None:
        return None
    if algorithm != "AES256" or key is None or md5 is None:
        return _INVALID_SSE_C
    raw = base64.b64decode(key)
    expected = base64.b64encode(hashlib.md5(raw, usedforsecurity=False).digest()).decode("ascii")
    return key if len(raw) == 32 and md5 == expected else _INVALID_SSE_C


class _StorageMixin:
    """R2 object storage: presigning, the SSE-C-aware `PUT`/`GET` handler, and key naming."""

    # Declared here so mypy would see them if tests were type-checked; the real values live on
    # `FakeVault.__init__` in `_core.py`, which every mixin shares through `self`.
    _objects: dict[str, bytes]
    _sse_keys: dict[str, str | None]
    _signed_sizes: dict[str, int]
    put_requests: list[httpx.Request]
    get_requests: list[httpx.Request]

    def _object_url(self, key: str) -> str:
        """A stable, opaque presigned-looking URL for one storage key."""
        return f"https://storage.diagnosusercontent.com/objects/{key}"

    def _signed_upload(self, url: str, size: int) -> dict[str, Any]:
        """`SignedUploadResponse`: the size is locked into the URL; SSE-C names ride alongside."""
        self._signed_sizes[url] = size
        return {
            "url": url,
            "method": "PUT",
            "headers": {"content-length": str(size), _SSE_C_ALGORITHM_HEADER: "AES256"},
            "client_headers": list(_SSE_C_CLIENT_HEADERS),
            "expires_at": 9_999_999_999,
        }

    @staticmethod
    def _signed_download(url: str) -> dict[str, Any]:
        """`SignedDownloadResponse`."""
        return {
            "url": url,
            "method": "GET",
            "headers": {_SSE_C_ALGORITHM_HEADER: "AES256"},
            "client_headers": list(_SSE_C_CLIENT_HEADERS),
            "expires_at": 9_999_999_999,
        }

    def handle_storage(self, request: httpx.Request) -> httpx.Response:
        """A `PUT`/`GET` against a presigned R2 URL, with R2's rules for size and SSE-C.

        A `PUT` must match the size the URL was signed for; an SSE-C key must
        match its MD5; a `GET` must present the same SSE-C key the object was
        written with (or none, if none) — R2 answers `400` otherwise.
        """
        url = str(request.url)
        sse_key = _sse_c_key_of(request)
        if sse_key is _INVALID_SSE_C:
            return httpx.Response(400)
        if request.method == "PUT":
            self.put_requests.append(request)
            signed = self._signed_sizes.get(url)
            if signed is not None and signed != len(request.content):
                return httpx.Response(403)
            self._objects[url] = request.content
            self._sse_keys[url] = sse_key  # type: ignore[assignment]
            etag = f'"{secrets.token_hex(8)}"'
            return httpx.Response(200, headers={"ETag": etag})
        if request.method == "GET":
            self.get_requests.append(request)
            data = self._objects.get(url)
            if data is None:
                return httpx.Response(404)
            if self._sse_keys.get(url) != sse_key:
                return httpx.Response(400)
            return httpx.Response(200, content=data)
        raise AssertionError(f"FakeVault: unexpected storage method {request.method}")
