#!/usr/bin/env python3
import json
import os
import time
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RELEASE = os.getenv("BRIDGE_RELEASE", "v6")
TOKEN = os.environ["BRIDGE_TOKEN"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
ANTHROPIC_PROXY_URL = os.getenv("ANTHROPIC_PROXY_URL", "").rstrip("/")
ANTHROPIC_PROXY_TOKEN = os.getenv("ANTHROPIC_PROXY_TOKEN", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "")
MAX_OUTPUT_TOKENS = max(64, min(int(os.getenv("BRIDGE_MAX_OUTPUT_TOKENS", "3000")), 3000))
MAX_HOPS = max(1, min(int(os.getenv("BRIDGE_MAX_HOPS", "4")), 8))
PORT = int(os.getenv("PORT", "8080"))
SERVER_INFO = {"name": "gpt-claude-bridge", "version": RELEASE}

def _post_json(url, payload, headers=None, timeout=120, attempts=3):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:2000]
            last = RuntimeError(f"HTTP {e.code}: {body}")
            if e.code < 500 and e.code not in (408, 409, 429):
                break
        except Exception as e:
            last = e
        if attempt + 1 < attempts:
            time.sleep(min(2 ** attempt, 4))
    raise RuntimeError(str(last or "request failed"))

def ask_claude(prompt, max_tokens=None):
    if not ANTHROPIC_PROXY_URL:
        raise RuntimeError("ANTHROPIC_PROXY_URL is not configured")
    if not ANTHROPIC_PROXY_TOKEN:
        raise RuntimeError("ANTHROPIC_PROXY_TOKEN is not configured")
    mt = max(32, min(int(max_tokens or MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS))
    payload = {"prompt": prompt, "max_tokens": mt}
    if ANTHROPIC_MODEL:
        payload["model"] = ANTHROPIC_MODEL
    out = _post_json(
        ANTHROPIC_PROXY_URL + "/call",
        payload,
        {"Authorization": "Bearer " + ANTHROPIC_PROXY_TOKEN},
        timeout=180,
    )
    text = out.get("text") if isinstance(out, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Claude returned empty output")
    return text.strip()

def _extract_openai_text(obj):
    if isinstance(obj, dict):
        direct = obj.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        chunks = []
        for item in obj.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            for c in item.get("content", []) or []:
                if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                    t = c.get("text")
                    if isinstance(t, str):
                        chunks.append(t)
        if chunks:
            return "".join(chunks).strip()
    return ""

def ask_gpt(prompt, max_tokens=None):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    mt = max(32, min(int(max_tokens or MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS))
    payload = {"model": OPENAI_MODEL, "input": prompt, "max_output_tokens": mt}
    out = _post_json(
        "https://api.openai.com/v1/responses",
        payload,
        {"Authorization": "Bearer " + OPENAI_API_KEY},
        timeout=180,
    )
    text = _extract_openai_text(out)
    if not text:
        raise RuntimeError("GPT returned empty output")
    return text

TOOLS = [
    {
        "name": "ask_gpt",
        "description": "Send a task or question to GPT through the private GPT-Claude bridge and return GPT's answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for GPT."},
                "max_tokens": {"type": "integer", "minimum": 32, "maximum": 3000}
            },
            "required": ["prompt"],
            "additionalProperties": False
        }
    },
    {
        "name": "ask_claude",
        "description": "Send a task or question to Claude through the private GPT-Claude bridge and return Claude's answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for Claude."},
                "max_tokens": {"type": "integer", "minimum": 32, "maximum": 3000}
            },
            "required": ["prompt"],
            "additionalProperties": False
        }
    },
    {
        "name": "ask_both",
        "description": "Send the same task to GPT and Claude and return both answers without ranking them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or question for both models."},
                "max_tokens": {"type": "integer", "minimum": 32, "maximum": 3000}
            },
            "required": ["prompt"],
            "additionalProperties": False
        }
    },
    {
        "name": "bridge_status",
        "description": "Return bridge configuration status without exposing any secrets.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}
    }
]

def _tool_call(name, args):
    args = args if isinstance(args, dict) else {}
    if name == "bridge_status":
        return json.dumps({
            "ok": True,
            "release": RELEASE,
            "openai_configured": bool(OPENAI_API_KEY),
            "claude_proxy_configured": bool(ANTHROPIC_PROXY_URL and ANTHROPIC_PROXY_TOKEN),
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_hops": MAX_HOPS
        }, ensure_ascii=False)
    prompt = args.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    mt = args.get("max_tokens")
    if name == "ask_gpt":
        return ask_gpt(prompt, mt)
    if name == "ask_claude":
        return ask_claude(prompt, mt)
    if name == "ask_both":
        result = {}
        errors = {}
        def run(key, fn):
            try:
                result[key] = fn(prompt, mt)
            except Exception as e:
                errors[key] = str(e)
        t1 = threading.Thread(target=run, args=("gpt", ask_gpt))
        t2 = threading.Thread(target=run, args=("claude", ask_claude))
        t1.start(); t2.start(); t1.join(); t2.join()
        return json.dumps({"answers": result, "errors": errors}, ensure_ascii=False)
    raise ValueError("Unknown tool")

def _modern_result(result):
    if isinstance(result, dict):
        result = dict(result)
        result.setdefault("resultType", "complete")
        result.setdefault("_meta", {"io.modelcontextprotocol/serverInfo": SERVER_INFO})
    return result

def handle_rpc(msg):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    rid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    modern = isinstance(params, dict) and isinstance(params.get("_meta"), dict) and params["_meta"].get("io.modelcontextprotocol/protocolVersion") == "2026-07-28"
    try:
        if method == "server/discover":
            result = {
                "supportedVersions": ["2026-07-28", "2025-11-25", "2025-06-18"],
                "capabilities": {"tools": {}},
                "instructions": "Use ask_gpt to consult GPT, ask_claude to consult Claude, ask_both for parallel independent answers, and bridge_status for diagnostics.",
                "ttlMs": 3600000,
                "cacheScope": "private",
                "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                "resultType": "complete"
            }
        elif method == "initialize":
            requested = params.get("protocolVersion", "2025-11-25") if isinstance(params, dict) else "2025-11-25"
            if requested not in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"):
                requested = "2025-11-25"
            result = {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": "Private GPT-Claude bridge."
            }
        elif method in ("notifications/initialized", "notifications/cancelled"):
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            answer = _tool_call(name, args)
            result = {"content": [{"type": "text", "text": answer}], "isError": False}
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
        if modern and method != "initialize":
            result = _modern_result(result)
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(e)[:2000]}}

class Handler(BaseHTTPRequestHandler):
    server_version = "GPTClaudeBridge/1.0"
    def log_message(self, fmt, *args):
        print("HTTP", self.address_string(), fmt % args, flush=True)

    def _json(self, status, obj, headers=None):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _authorized_path(self):
        return self.path.split("?", 1)[0] == f"/mcp/{TOKEN}"

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type, accept, mcp-protocol-version, mcp-method, mcp-name")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._json(200, {
                "ok": True,
                "release": RELEASE,
                "openai": bool(OPENAI_API_KEY),
                "claude": bool(ANTHROPIC_PROXY_URL and ANTHROPIC_PROXY_TOKEN)
            })
        if path == f"/selftest/{TOKEN}":
            checks = {}
            for key, fn, expected in (
                ("gpt", ask_gpt, "BRIDGE_SELFTEST_GPT_OK"),
                ("claude", ask_claude, "BRIDGE_SELFTEST_CLAUDE_OK"),
            ):
                try:
                    answer = fn("Reply exactly: " + expected, 64)
                    checks[key] = {"ok": answer.strip() == expected, "text": answer[:200]}
                except Exception as e:
                    checks[key] = {"ok": False, "error": str(e)[:500]}
            ok = all(v.get("ok") for v in checks.values())
            return self._json(200 if ok else 503, {"ok": ok, "release": RELEASE, "checks": checks})
        if self._authorized_path():
            return self._json(200, {"ok": True, "mcp": True, "release": RELEASE})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._authorized_path():
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                return self._json(413, {"error": "invalid body size"})
            msg = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        response = handle_rpc(msg)
        if response is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return self._json(200, response)

if __name__ == "__main__":
    print(json.dumps({
        "event": "bridge_boot",
        "release": RELEASE,
        "port": PORT,
        "openai": bool(OPENAI_API_KEY),
        "claude_proxy": bool(ANTHROPIC_PROXY_URL and ANTHROPIC_PROXY_TOKEN),
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_hops": MAX_HOPS
    }), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
