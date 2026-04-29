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
SUMMARY_KEYS = {
    "call_id",
    "id",
    "item_reference",
    "name",
    "previous_response_id",
    "tool_use_id",
    "type",
}


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


def compact(value, max_length=120):
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def compact_json(value, max_length=12000):
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def extract_tool_result_text(block):
    content = block.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type", "unknown")
                if item_type == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(f"[{item_type} omitted]")
        return "\n".join(part for part in parts if part)
    if content:
        return str(content)
    if block.get("is_error"):
        return "[tool returned an error]"
    return "[empty tool result]"


def text_block(text):
    return {"type": "text", "text": text}


def normalize_tool_history(value):
    """Convert Claude Code historical tool blocks to text for tokenhubpro.

    tokenhubpro's OpenAI Responses HTTP bridge rejects Anthropic tool_result
    history because it expects Responses item_reference IDs. Claude Code still
    executes tools locally; this only changes how prior tool calls/results are
    represented to the upstream model.
    """
    if isinstance(value, dict):
        block_type = value.get("type")
        if block_type == "tool_use":
            name = value.get("name", "unknown")
            tool_id = value.get("id", "unknown")
            tool_input = compact_json(value.get("input", {}))
            return text_block(
                f"[Claude Code tool call]\n"
                f"name: {name}\n"
                f"id: {tool_id}\n"
                f"input: {tool_input}"
            )
        if block_type == "tool_result":
            tool_id = value.get("tool_use_id", "unknown")
            result = compact_json(extract_tool_result_text(value), max_length=30000)
            status = "error" if value.get("is_error") else "ok"
            return text_block(
                f"[Claude Code tool result]\n"
                f"tool_use_id: {tool_id}\n"
                f"status: {status}\n"
                f"result: {result}"
            )
        return {key: normalize_tool_history(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_tool_history(item) for item in value]
    return value


def summarize_payload(value, path="$", lines=None, limit=80):
    if lines is None:
        lines = []
    if len(lines) >= limit:
        return lines

    if isinstance(value, dict):
        interesting = {key: value.get(key) for key in SUMMARY_KEYS if key in value}
        if interesting:
            rendered = ", ".join(f"{key}={compact(val)}" for key, val in sorted(interesting.items()))
            lines.append(f"{path}: {rendered}")
        for key, item in value.items():
            if key in {"authorization", "api_key", "ANTHROPIC_AUTH_TOKEN"}:
                continue
            summarize_payload(item, f"{path}.{key}", lines, limit)
            if len(lines) >= limit:
                break
    elif isinstance(value, list):
        for index, item in enumerate(value):
            summarize_payload(item, f"{path}[{index}]", lines, limit)
            if len(lines) >= limit:
                break
    return lines


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
        summary = []

        if body and "json" in content_type:
            try:
                payload = json.loads(body)
                summary = summarize_payload(payload)
                payload = normalize_tool_history(payload)
                payload = scrub(payload, removed)
                body = json.dumps(payload, separators=(",", ":")).encode()
            except json.JSONDecodeError:
                pass

        self.forward(body, removed, summary)

    def write_log(self, message):
        print(message, file=sys.stderr, flush=True)

    def forward(self, body, removed=None, summary=None):
        removed = removed or []
        summary = summary or []
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
            if exc.code >= 400 and summary:
                self.write_log("request summary:")
                for line in summary:
                    self.write_log(f"  {line}")
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
