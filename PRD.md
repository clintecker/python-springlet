# Spring ’83 Home‑Lab Stack — Product Requirements Document (PRD)

*Version 0.1 — April 23 2025*

---

## 1. Purpose
Provide a minimal, reproducible reference implementation of the **Spring ’83** protocol that can be built, tested, and deployed automatically by a coding LLM.
The stack must run self‑hosted on the user’s Proxmox cluster and include:

1. A **Python server** that implements the “happy path” of the June 2022 Spring ’83 draft spec.
2. A **Python CLI client** that fetches boards listed in `~/.83`.
3. **Infrastructure as Code** (IaC) files to deploy the server behind **Caddy 3** with automatic HTTPS.
4. **Automation**: systemd service units, log‑rotation, cron TTL cleanup.
5. **CI pipeline** (GitHub Actions) that lints, tests, and builds a container image.

The result will live in a single Git repo and bootstrap from `git clone` → `make deploy`.

---

## 2. Scope
### 2.1 In‑Scope
| Area | Details |
|------|---------|
| **Protocol** | Implement GET/PUT/OPTIONS endpoints, signature verify, 2217‑byte limit, 22‑day TTL, CORS, deny/test keys. |
| **Server language** | CPython ≥3.9, stdlib only + vendored **pure25519**. |
| **Client language** | Same constraints. |
| **Packaging** | Poetry or plain `requirements.txt` (no compiled wheels). |
| **Deployment** | Debian 12 LXC, Caddy 3 reverse proxy, systemd units. |
| **Security** | TLS via Caddy, firewall rules (Promox + UFW), rate limiting. |
| **Testing** | Unit tests for key validation, signature verify, HTTP handlers; smoke test script that publishes + fetches a board. |

### 2.2 Out‑of‑Scope (MVP)
* Full history or persistence beyond flat files.
* Web UI / fancy client UX.
* Image/video support (Spring ’83+).

---

## 3. Functional Requirements
### 3.1 Server (`spring83_server.py`)
1. **Listen** on `127.0.0.1:8083` (plain HTTP); Caddy terminates TLS.
2. **Endpoints**
   * `OPTIONS /` — CORS headers.
   * `GET /` — minimal HTML with operator info & TTL.
   * `PUT /<key>` — publish board.
   * `GET /<key>` — retrieve board.
3. **Validation**
   * Key format regex `^[0-9a-f]{57}83e(0[1-2][0-9])\d{2}$`.
   * Board ≤2217 bytes, contains single `<time>` ISO‑UTC element.
   * Signature using Ed25519 (pure Python).
   * Timestamp ≤ now, ≥22 days past, monotonic vs stored copy.
4. **Storage**
   * Flat‑file under `/opt/spring83/boards/<key>`; filename == key.
   * Cron cleanup after 22 days.
5. **Deny/Test Keys**
   * Reject infernal key `d17eef…0123`.
   * Serve rotating content for test key `ab589f…0583`.
6. **Performance** — Service ≤50 req/s on Raspberry Pi 4.

### 3.2 Client (`spring83_client.py`)
1. Read `~/.83` (one URL per line, `#` comments allowed).
2. GET each board with `Spring-Version: 83` and `If-Modified-Since` from cache.
3. Cache under `~/.83_cache/<key>.html` and print status.
4. Pure stdlib, no signature validation (stretch goal flag `--verify`).

---

## 4. Non‑Functional Requirements
* **Security**: Only port 443 exposed; Caddy rate‑limits 30 req/10 s.
* **Reliability**: systemd restarts on failure; uptime goal 99.9 %.
* **Maintainability**: ≤300 LOC server, ≤150 LOC client; extensive docstrings.
* **Portability**: Works on Debian 12/Ubuntu 24.04/Alpine 3.20.

---

## 5. Architecture
```text
+------------+        HTTPS       +-----------+
|  Internet  |  ───► 443 (Caddy) ─► Spring83  |
+------------+                    |  Server   |
                                   +-----------+
                                    ^ 127.0.0.1:8083
                                    |
                           Flat‑file boards store
```

---

## 6. Repository Layout
```
spring83/
├─ server/
│  ├─ spring83_server.py
│  ├─ service/spring83.service      # systemd unit
│  ├─ tests/
│  └─ boards/  (git‑ignored)
├─ client/
│  └─ spring83_client.py
├─ deploy/
│  ├─ Caddyfile
│  ├─ lxc_setup.sh
│  └─ cron/cleanup.sh
├─ .github/workflows/ci.yml
├─ LICENSE (MIT)
└─ README.md
```

---

## 7. Deployment Flow (Makefile targets)
| Target | Action |
|--------|--------|
| `make setup` | `python -m venv`, install deps, pre‑commit hooks. |
| `make test` | Run pytest & flake8. |
| `make lxc` | Execute `deploy/lxc_setup.sh` to create & configure container on Proxmox via `pct`. |
| `make deploy` | rsync files into CT, enable systemd service, reload Caddy. |

---

## 8. CI Pipeline (GitHub Actions)
1. Matrix: `python-versions: [3.9, 3.10, 3.11]`.
2. Jobs: lint (ruff), test (pytest), build (docker), publish image to GHCR (optional).
3. On `main` push & PRs.

---

## 9. Deliverables
* Source code (server, client) with unit tests.
* `Caddyfile`, systemd units, cron cleanup script.
* Automated CI pipeline.
* README with quick‑start.
* CHANGELOG.md.

---

## 10. Acceptance Criteria
1. End‑to‑end script publishes a board and client fetches it on fresh clone.
2. `pytest` green.
3. `curl -H 'Spring-Version: 83' https://domain/key` returns board w/ correct headers.
4. Container passes `lynis audit` score >70.

---

## 11. Milestones
| Date | Milestone |
|------|-----------|
| T+0 | Repo scaffold committed. |
| T+2d| Server MVP passes unit tests. |
| T+4d| Client MVP functional. |
| T+5d| Deployment scripts tested on Proxmox. |
| T+7d| CI/CD pipeline green; v0.1 tag. |

---

## 12. Appendix A — Key Regex & Constants
```python
KEY_RE = re.compile(r"^[0-9a-f]{57}83e(0[1-9]|1[0-2])\d{2}$")
INFERNAL_KEY = "d17eef211f510479ee6696495a2589f7e9fb055c2576749747d93444883e0123"
TEST_KEY     = "ab589f4dde9fce4180fcf42c7b05185b0a02a5d682e353fa39177995083e0583"
BOARD_LIMIT  = 2217
TTL_SECONDS  = 22 * 24 * 3600
```
