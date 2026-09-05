"""
agent/src/tools/file_tools.py
文件工具：list/read/write。
攻击面：真实业务 agent 常暴露"任意路径读写"。这里故意保留，
但路径被强制限制在靶场内(仅容器内的 /targets 和 /workspace)，绝不触及宿主机。
"""
import os
from pathlib import Path

# 靶场内允许访问的沙箱根（容器内部路径，非宿主机）
READ_ROOT = Path("/targets")          # 只读数据（compose 只读挂载）
WRITE_ROOT = Path("/workspace")       # 可写工作区（纯容器内，不挂载宿主机）

# ===== 加固策略 =====
# 敏感文件/路径黑名单：命中即拒绝读取（防漏洞1）
SENSITIVE_PATTERNS = [
    "secrets",      # /targets/secrets/*
    "db.conf",      # 配置文件
    ".env",         # 环境变量
    "password",     # 含密码
    "secret",       # 含机密
    "credential",   # 凭据
    "key" + ".pem", "id_rsa", "shadow", "passwd",  # 密钥/系统文件
]
# 敏感信息脱敏正则（返回前替换，防值泄露）
REDACT_PATTERNS = [
    (r"(?i)(password\s*[=:]?\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(passwd\s*[=:]?\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(secret_key\s*[=:]?\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(api[_-]?key\s*[=:]?\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(token\s*[=:]?\s*)\S+", r"\1[REDACTED]"),
    (r"SuperSecret[^\s,;\"]*", "[REDACTED]"),
]


def _is_sensitive(rel: str) -> bool:
    """判断路径是否命中敏感黑名单。"""
    low = rel.lower()
    return any(p in low for p in SENSITIVE_PATTERNS)


def _redact(text: str) -> str:
    """对返回内容做敏感信息脱敏。"""
    import re
    for pat, repl in REDACT_PATTERNS:
        text = re.sub(pat, repl, text)
    return text


def _safe_resolve(base: Path, rel: str) -> Path:
    """把相对路径解析到沙箱内，防路径穿越逃逸到沙箱外。"""
    # 处理空/根路径：直接指向 base
    if rel in ("", "/", "."):
        return base
    p = (base / rel).resolve()
    # 必须仍在 base 之内
    if not str(p).startswith(str(base) + "/") and str(p) != str(base):
        raise PermissionError(f"路径越界被拒绝: {rel}")
    return p


def list_files(path: str = "/") -> str:
    """列出沙箱内目录下的文件。敏感目录隐藏。"""
    p = _safe_resolve(READ_ROOT, path)
    if not p.is_dir():
        return f"错误: {path} 不是目录"
    items = []
    for x in sorted(p.iterdir()):
        # 隐藏敏感目录/文件（防枚举 secrets）
        if _is_sensitive(x.name):
            continue
        items.append(x.name)
    return "\n".join(items)


def read_file(path: str) -> str:
    """读取沙箱内文本文件内容。敏感文件拒绝，返回内容脱敏。"""
    p = _safe_resolve(READ_ROOT, path)
    if not p.is_file():
        return f"错误: 文件不存在 {path}"
    # 敏感路径黑名单拦截（防漏洞1）
    rel = str(p.relative_to(READ_ROOT))
    if _is_sensitive(rel):
        return "访问被拒绝: 该文件属于敏感/机密路径，无读取权限"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:8000]
        # 返回前脱敏，防值泄露
        return _redact(text)
    except Exception as e:
        return f"读取失败: {e}"


def write_file(path: str, content: str) -> str:
    """写入文件到容器内工作区(非宿主机)。含敏感内容时拒绝(防漏洞2)。"""
    # 敏感来源溯源：若内容含机密特征则拒绝
    if _is_sensitive(content):
        return "写入被拒绝: 内容疑似包含敏感/机密信息"
    p = _safe_resolve(WRITE_ROOT, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {p} ({len(content)} 字节)"
