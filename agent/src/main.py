"""
agent/src/main.py
靶机 agent 主程序 —— 一个通过 HTTP 暴露、能调用工具的 agent。

工作方式：
  1. 接收用户指令（HTTP POST）
  2. 发给 OpenRouter（function-calling）
  3. 循环：模型→工具调用→执行→把结果回喂模型→最终回答
  4. 返回最终回复

安全：工具全部限定在靶场容器内；本服务只监听 lab_internal 网内端口，
不暴露宿主机。
"""
import os
import json
import re
import http.server
import socket

from openai import OpenAI

from .tools import TOOLS_SCHEMA, FUNCS, SYSTEM_PROMPT

OPENROUTER_BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("OPENROUTER_MODEL", "cohere/north-mini-code:free")
MAX_ITERS = 10


def _client():
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)


def run_agent(client, user_msg: str) -> str:
    """执行一次 agent 对话循环，返回最终回复。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    for _ in range(MAX_ITERS):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )
        msg = resp.choices[0].message

        # 无工具调用 → 直接返回
        if not msg.tool_calls:
            return msg.content or "(空回复)"

        # 有工具调用 → 执行并回喂
        tool_msgs = [{"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]}]
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            fn = FUNCS.get(name)
            if not fn:
                result = f"未知工具: {name}"
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = f"工具执行错误: {e}"
            tool_msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })
        messages.extend(tool_msgs)
    return "(达到最大迭代次数)"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            user_msg = body.get("message", "")
            if not user_msg:
                self._send(400, {"error": "missing 'message'"})
                return
            client = _client()
            reply = run_agent(client, user_msg)
            self._send(200, {"reply": reply})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_GET(self):
        self._send(200, {"status": "alive", "model": MODEL, "tools": list(FUNCS.keys())})

    def _send(self, code, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # 静默


def get_internal_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    port = 8000
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[agent] 靶机 agent 已启动，监听 {port}，模型={MODEL}")
    print(f"[agent] 可用工具: {', '.join(FUNCS.keys())}")
    print(f"[agent] 容器内网IP: {get_internal_ip()}")
    server.serve_forever()
