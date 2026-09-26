"""🇺🇸 The agent's wire: JSON lines, split or batched however the socket delivers them, and nothing else.

🇧🇷 O fio do agente: linhas JSON, partidas ou juntas como o socket as entregar, e nada além disso.
"""

from __future__ import annotations

import io
import socket
import threading
from collections.abc import Iterator

import pytest
from diagnos_cli.agent import protocol
from diagnos_cli.agent.server import _Input, _Stream


@pytest.fixture
def pair() -> Iterator[tuple[socket.socket, socket.socket]]:
    """🇺🇸 Two connected sockets. 🇧🇷 Dois sockets conectados."""
    left, right = socket.socketpair()
    with left, right:
        yield left, right


def test_frames_round_trip_with_non_ascii_text(pair: tuple[socket.socket, socket.socket]) -> None:
    """🇺🇸 UTF-8 as is — a patient named "João" arrives as "João". 🇧🇷 UTF-8 como é — "João" chega como "João"."""
    left, right = pair
    protocol.send(left, {"type": "out", "data": "João · ação\n"})
    assert protocol.Reader(right).next() == {"type": "out", "data": "João · ação\n"}


def test_reader_splits_batched_frames_and_joins_split_ones(pair: tuple[socket.socket, socket.socket]) -> None:
    """🇺🇸 Two frames in one packet, then one frame over two packets. 🇧🇷 Dois frames num pacote, depois um em dois."""
    left, right = pair
    reader = protocol.Reader(right)
    left.sendall(b'{"type":"a"}\n{"type":"b"}\n{"type":')
    assert reader.next() == {"type": "a"}
    assert reader.next() == {"type": "b"}
    left.sendall(b'"c"}\n')
    assert reader.next() == {"type": "c"}


def test_reader_returns_none_when_the_peer_closes(pair: tuple[socket.socket, socket.socket]) -> None:
    """🇺🇸 A closed connection is `None`, not an error. 🇧🇷 Uma conexão fechada é `None`, não um erro."""
    left, right = pair
    left.close()
    assert protocol.Reader(right).next() is None


@pytest.mark.parametrize("raw", [b"not json\n", b"[1, 2]\n", b'{"data": "x"}\n', b'{"type": 3}\n'])
def test_reader_rejects_anything_but_a_typed_object(pair: tuple[socket.socket, socket.socket], raw: bytes) -> None:
    """🇺🇸 Non-JSON, non-objects and a missing or non-string `type` are violations.

    🇧🇷 Não-JSON, não-objetos e um `type` ausente ou não string são violações.
    """
    left, right = pair
    left.sendall(raw)
    with pytest.raises(protocol.ProtocolViolation):
        protocol.Reader(right).next()


def test_reader_refuses_an_endless_line(
    monkeypatch: pytest.MonkeyPatch, pair: tuple[socket.socket, socket.socket]
) -> None:
    """🇺🇸 A peer that never sends a newline cannot make the reader buffer forever.

    🇧🇷 Um par que nunca manda quebra de linha não faz o leitor acumular para sempre.
    """
    monkeypatch.setattr(protocol, "MAX_FRAME_BYTES", 16)
    left, right = pair
    left.sendall(b"x" * 64)
    with pytest.raises(protocol.ProtocolViolation, match="too large"):
        protocol.Reader(right).next()


def test_stream_sends_text_and_behaves_like_a_text_stream(pair: tuple[socket.socket, socket.socket]) -> None:
    """🇺🇸 Text becomes a frame; empty text sends nothing; bytes are refused (Click probes with `write(b"")`).

    🇧🇷 Texto vira um frame; texto vazio não manda nada; bytes são recusados (o Click testa com `write(b"")`).
    """
    left, right = pair
    stream = _Stream(left, threading.Lock(), "err", tty=True)
    assert stream.write("") == 0
    assert stream.write("olá") == 3
    assert protocol.Reader(right).next() == {"type": "err", "data": "olá"}
    with pytest.raises(TypeError):
        stream.write(b"")  # type: ignore[arg-type]
    with pytest.raises(io.UnsupportedOperation):
        stream.fileno()
    assert stream.isatty() is True
    assert stream.encoding == "utf-8"
    stream.flush()


def test_input_asks_the_client_for_each_line(pair: tuple[socket.socket, socket.socket]) -> None:
    """🇺🇸 `readline` sends a prompt frame and returns the reply; anything else is end of input.

    🇧🇷 `readline` manda um frame de prompt e devolve a resposta; qualquer outra coisa é fim da entrada.
    """
    agent_side, client_side = pair
    stdin = _Input(agent_side, protocol.Reader(agent_side), threading.Lock())
    protocol.send(client_side, {"type": "input", "line": "y\n"})
    assert stdin.readline() == "y\n"
    protocol.send(client_side, {"type": "out", "data": "confused"})
    assert stdin.readline() == ""
    client_reader = protocol.Reader(client_side)
    assert client_reader.next() == {"type": "prompt"}
    assert client_reader.next() == {"type": "prompt"}
    client_side.close()
    assert stdin.readline() == ""
    assert stdin.isatty() is False
    with pytest.raises(io.UnsupportedOperation):
        stdin.fileno()
