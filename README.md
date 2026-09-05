# AI Agent Red-Teaming Lab

An **isolated, containerized security lab** for red-teaming AI Agent systems — reproducing real-world attack surfaces (prompt injection, tool abuse, privilege escalation, unauthorized SQL, data exfiltration) inside a controlled sandbox, and validating defenses through an **attack → defend → re-test closed loop**.

## Security Isolation

- 100% Docker-containerized, dedicated `lab_internal` network
- No host port mapping, no host sensitive-directory mounts, resource+pids limits, `no-new-privileges`
- Fully isolated from host and other containers
- Remote inference via OpenRouter (no local LLM, low resource use)

## Key Findings (attack → defend loop)

| | Before hardening | After hardening |
|---|---|---|
| Confirmed high-severity vulns | **3** (plaintext secret read / SQL escalation / data exfiltration) | **0** (all blocked at tool layer) |
| Inducible destructive SQL | Present | Refused |
| Normal business reads | — | Unaffected (no collateral damage) |

**Core principle demonstrated**: *never trust the LLM to follow natural-language rules — enforce privileges at the tool/system layer.*

## Contents

```
agent/          Target agent image (file/db/sql/net tools) + hardening
redteam/        Attacker side (attack script, Garak/PyRIT deps)
targets/        Fake data sandbox (secrets config, employee table)
attack-reports/ Raw attack data + final reports
docs/           Bilingual/trilingual documentation (zh / en / ja)
  zh/ 中文文档
  en/ English docs
  ja/ 日本語ドキュメント
scripts/        PDF generation
```

## Quick Start

```bash
docker compose up -d
# Health check from redteam container:
docker exec redteam-attacker python3 -c \
  "import urllib.request; print(urllib.request.urlopen('http://redteam-agent:8000/', timeout=10).read().decode())"
# Run attack suite:
docker exec redteam-attacker python3 /redteam/scripts/attack_agent.py
```

> **Note**: `.env` holds the OpenRouter key. Set your own key before use; it is gitignored.

## Documentation

- [环境说明](docs/zh/01-environment.md) · [Environment](docs/en/01-environment.md) · [環境説明](docs/ja/01-environment.md)
- [漏洞报告](docs/zh/02-vulnerability-report.md) · [Vuln Report](docs/en/02-vulnerability-report.md) · [脆弱性報告](docs/ja/02-vulnerability-report.md)
- [加固对比](docs/zh/03-hardening-comparison.md) · [Hardening](docs/en/03-hardening-comparison.md) · [堅牢化比較](docs/ja/03-hardening-comparison.md)

## License

Private — all data is fictional lab data for security research. Not for production use.
