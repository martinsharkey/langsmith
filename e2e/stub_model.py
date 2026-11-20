#!/usr/bin/env python3
"""A deterministic stand-in for the LLM Gateway, for end-to-end tests only.

Speaks the OpenAI Chat Completions format (streaming and non-streaming) and replies by simple rules, so a test run
needs no model, no GPU and no network:

- the last message is a tool result  -> a final text answer quoting it
- the user asks to "publish"         -> a `publish_document` tool call (which the agent must pause on)
- the user asks for a "plan"         -> a `write_todos` tool call
- anything else                      -> a short text reply
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def decide(messages: list[dict]) -> dict:
    last = messages[-1] if messages else {}
    if last.get("role") == "tool":
        return {"content": f"Finished: {text_of(last.get('content'))}"}
    user = next((text_of(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), "")
    lowered = user.lower()
    if "publish" in lowered:
        return {"tool": "publish_document", "args": {"title": "Design", "body": "Approved text"}}
    if "plan" in lowered:
        return {"tool": "write_todos", "args": {"todos": [
            {"content": "Draft the design", "status": "in_progress"},
            {"content": "Review the draft", "status": "pending"},
        ]}}
    return {"content": f"Stub model reply: {user}"}


def message_for(decision: dict) -> tuple[dict, str]:
    if "tool" in decision:
        call = {"id": "call_e2e_1", "type": "function",
                "function": {"name": decision["tool"], "arguments": json.dumps(decision["args"])}}
        return {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
    return {"role": "assistant", "content": decision["content"]}, "stop"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # one line per request on stderr
        sys.stderr.write("stub-model: " + fmt % args + "\n")

    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": "custom/class-m", "object": "model"},
                                                        {"id": "custom/class-s", "object": "model"}]})
        else:
            self._json(200, {"status": "ok"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json(404, {"error": {"message": "only /chat/completions is implemented"}})
            return
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            self._json(401, {"error": {"message": "missing gateway key"}})
            return
        model = request.get("model", "custom/class-m")
        message, finish = message_for(decide(request.get("messages", [])))
        base = {"id": "chatcmpl-e2e", "created": 0, "model": model}
        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        if not request.get("stream"):
            self._json(200, {**base, "object": "chat.completion", "usage": usage,
                             "choices": [{"index": 0, "message": message, "finish_reason": finish}]})
            return
        delta = dict(message)
        if delta.get("tool_calls"):
            delta["tool_calls"] = [{**call, "index": i} for i, call in enumerate(delta["tool_calls"])]
        chunks = [
            {**base, "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {**base, "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
        ]
        if (request.get("stream_options") or {}).get("include_usage"):
            chunks.append({**base, "object": "chat.completion.chunk", "choices": [], "usage": usage})
        body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
