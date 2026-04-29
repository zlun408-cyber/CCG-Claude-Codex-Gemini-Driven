#!/usr/bin/env python3
"""Small Claude Code compatibility proxy for tokenhubpro.

Claude Code interactive mode can send newer Responses fields that tokenhubpro's
Anthropic-compatible endpoint currently rejects. This proxy keeps the normal
Claude Code TUI, but removes known-incompatible request keys before forwarding.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DROP_KEYS = {"output_config", "temperature", "previous_response_id"}


def scrub(value, removed=None, path="$"):
    if removed is None:
        removed = []
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key in DROP_KEYS:
                removed.append(item_path)
                continue
            result[key] = scrub(item, removed, item_path)
        return result
    if isinstance(value, list):
        return [scrub(item, removed, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


class ProxyHandler(BaseHTTPRequestHandler):
    upstream = "https://tokenhubpro.com"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.forward(None)

    def do_OPTIONS(self):
        self.forward(None)

    def do_POST(self):
        self.forward_with_body()

    def do_PUT(self):
        self.forward_with_body()

    def do_PATCH(self):
        self.forward_with_body()

    def do_DELETE(self):
        self.forward_with_body()

    def forward_with_body(self):
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        content_type = self.headers.get("content-type", "")
        removed = []

        if body and "json" in content_type:
            try:
                payload = scrub(json.loads(body), removed)
                body = json.dumps(payload, separators=(",", ":")).encode()
            except json.JSONDecodeError:
                pass

        self.forward(body, removed)

    def write_log(self, message):
        print(message, file=sys.stderr, flush=True)

    def forward(self, body, removed=None):
        removed = removed or []
        url = self.upstream.rstrip("/") + self.path
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "accept-encoding"}
        }
        if body is not None:
            headers["content-length"] = str(len(body))

        self.write_log(
            f"> {self.command} {self.path} "
            f"len={len(body) if body is not None else 0} "
            f"removed={','.join(removed) if removed else '-'}"
        )

        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = response.read()
                self.write_log(f"< {response.status} {self.command} {self.path} bytes={len(data)}")
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"transfer-encoding", "content-encoding", "connection"}:
                        self.send_header(key, value)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as exc:
            data = exc.read()
            self.write_log(f"< {exc.code} {self.command} {self.path} bytes={len(data)}")
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in {"transfer-encoding", "content-encoding", "connection"}:
                    self.send_header(key, value)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            data = json.dumps({"error": str(exc)}).encode()
            self.write_log(f"< 502 {self.command} {self.path} error={exc}")
            self.send_response(502)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=51742)
    parser.add_argument("--upstream", default="https://tokenhubpro.com")
    args = parser.parse_args()

    ProxyHandler.upstream = args.upstream
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ProxyHandler)
    print(f"claude gateway proxy listening on 127.0.0.1:{args.port}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
