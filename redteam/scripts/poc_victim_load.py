#!/usr/bin/env python3
"""
CVE-2025-32434 / pickle RCE — 受害者加载模拟 (safe)

模拟一个"开发者加载了不可信模型文件"的场景:
  - 真实环境: torch.load("malicious.pt")  或 pickle.load(...)
  - 本演示用 pickle.loads(...) 复现相同机制 (torch.load 底层就是 pickle)
运行后会在 /tmp 生成 rce_demo 文件并打印 id —— 证明加载即执行。

安全性: 仅无害命令, 在隔离容器内。
"""
import pickle
import os
import sys

# 目标文件 (由 poc_build_malicious.py 生成到 /tmp)
TARGETS = [
    "/tmp/malicious_model.pkl",
    "/tmp/malicious_model.pt",
]


def load_pickle(path: str) -> object:
    """等价于 torch.load(path) —— 反序列化并返回对象 (这里是触发点)。"""
    with open(path, "rb") as f:
        return pickle.load(f)  # ← 恶意 __reduce__ 在此触发


def main():
    print("[*] 模拟受害者加载不可信模型文件...\n")
    for path in TARGETS:
        if not os.path.exists(path):
            continue
        print(f"[*] 加载: {path}")
        # 验证 /tmp 文件在加载前不存在
        if os.path.exists("/tmp/rce_demo"):
            os.remove("/tmp/rce_demo")
        try:
            load_pickle(path)
        except Exception as e:
            print(f"    加载异常: {e}")

    # 验证 RCE 是否触发 (rce_demo 文件是否被创建)
    if os.path.exists("/tmp/rce_demo"):
        print("\n[✔] RCE 触发成功: /tmp/rce_demo 文件被创建")
        print("    → 证明: 加载不可信 pickle 文件 = 任意代码执行")
    else:
        print("\n[!] 未检测到触发文件")


if __name__ == "__main__":
    main()
