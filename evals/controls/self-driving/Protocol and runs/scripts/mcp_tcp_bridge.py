#!/usr/bin/env python3
"""Bridge MCP stdio across a private TCP connection.

Run with ``server`` beside the credentialed MCP process and ``client`` inside
the research-agent container. The agent can exchange MCP messages without
receiving the server's environment or filesystem.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading


def copy(source, destination) -> None:
    try:
        while chunk := os.read(source.fileno(), 65536):
            view = memoryview(chunk)
            while view:
                written = os.write(destination.fileno(), view)
                view = view[written:]
    except (BrokenPipeError, ConnectionError, OSError):
        pass
    finally:
        try:
            destination.close()
        except OSError:
            pass


def serve_connection(connection: socket.socket, command: list[str]) -> None:
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert process.stdin is not None and process.stdout is not None
    incoming = connection.makefile("rb", buffering=0)
    outgoing = connection.makefile("wb", buffering=0)
    threads = [
        threading.Thread(target=copy, args=(incoming, process.stdin), daemon=True),
        threading.Thread(target=copy, args=(process.stdout, outgoing), daemon=True),
    ]
    for thread in threads:
        thread.start()
    process.wait()
    connection.close()


def server(host: str, port: int, command: list[str]) -> None:
    with socket.create_server((host, port), reuse_port=False) as listener:
        while True:
            connection, _ = listener.accept()
            threading.Thread(
                target=serve_connection, args=(connection, command), daemon=True
            ).start()


def client(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=30) as connection:
        connection.settimeout(None)
        incoming = connection.makefile("rb", buffering=0)
        outgoing = connection.makefile("wb", buffering=0)
        threads = [
            threading.Thread(target=copy, args=(sys.stdin.buffer, outgoing), daemon=True),
            threading.Thread(target=copy, args=(incoming, sys.stdout.buffer), daemon=True),
        ]
        for thread in threads:
            thread.start()
        threads[1].join()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("server", "client"))
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == "server":
        command = args.command or ["aeris-mcp"]
        server(args.host, args.port, command)
    else:
        client(args.host, args.port)


if __name__ == "__main__":
    main()
