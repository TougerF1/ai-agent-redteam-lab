#!/usr/bin/env python3
"""
PyTorch RCE 防御演示 — weights_only=True 机制 (safe)

真实修复: torch.load(path, weights_only=True)
  - 底层用受限的 Unpickler, 通过重写 find_class() 只允许"权重张量相关"类
  - 拒绝任意类构造 (如 os.system) → 恶意 __reduce__ 无法触发

本演示用 pickle.Unpickler + find_class 钩子复现同样的防护机制,
证明同一份恶意文件 + 安全加载 = RCE 被阻止。无需安装 PyTorch。

用法: python3 poc_defense_weightsonly.py
"""
import pickle
import os
import sys

MALICIOUS = "/tmp/malicious_model.pt"


class SafeUnpickler(pickle.Unpickler):
    """模拟 torch.load(weights_only=True) 的受限反序列化器。"""

    # 只允许"权重张量"白名单类 (真实 torch 限制为 torch.*Tensor 等)
    ALLOWED = {
        ("torch", "Tensor"),
        ("torch", "FloatStorage"),
        ("collections", "OrderedDict"),
    }

    def find_class(self, module, name):
        if (module, name) not in self.ALLOWED:
            raise pickle.UnpicklingError(
                f"[BLOCKED] 拒绝加载: {module}.{name} "
                f"(weights_only 模式禁止任意类)"
            )
        return super().find_class(module, name)


def load_safe(path: str):
    """等价于 torch.load(path, weights_only=True)。"""
    with open(path, "rb") as f:
        return SafeUnpickler(f).load()


def main():
    print("=" * 62)
    print("  PyTorch RCE 防御演示: weights_only=True 机制")
    print("=" * 62)
    print(f"[*] 加载文件: {MALICIOUS}")

    # 防御前: 常规 pickle.load (模拟有漏洞的 torch.load 默认行为)
    if os.path.exists("/tmp/rce_demo"):
        os.remove("/tmp/rce_demo")
    print("\n[*] 不安全的加载 (模拟 torch.load 默认 / CVE-2025-32434)...")
    try:
        with open(MALICIOUS, "rb") as f:
            pickle.load(f)
        print(f"    [!!] RCE 触发: /tmp/rce_demo → {os.path.exists('/tmp/rce_demo')}")
    except Exception as e:
        print(f"    [!!] RCE 触发: /tmp/rce_demo → {os.path.exists('/tmp/rce_demo')}")

    # 防御后: weights_only 安全加载
    if os.path.exists("/tmp/rce_demo"):
        os.remove("/tmp/rce_demo")
    print("\n[*] 安全加载 (torch.load weights_only=True)...")
    try:
        load_safe(MALICIOUS)
        print("    [WARNING] 未拦截? (不应出现)")
    except pickle.UnpicklingError as e:
        print(f"    [✔] 攻击被阻止: {str(e)[:60]}")
    finally:
        print(f"    RCE 触发验证: /tmp/rce_demo 存在 = {os.path.exists('/tmp/rce_demo')}")

    print("\n" + "=" * 62)
    print("  结论: 同一份恶意文件, 安全加载 (weights_only) 成功阻断 RCE。")


if __name__ == "__main__":
    main()
