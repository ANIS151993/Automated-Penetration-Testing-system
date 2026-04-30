# PentAI Pro

<div align="center">

**An LLM-Powered Automated Penetration Testing Platform**  
*Self-Hosted · Scope-Safe · Audit-Logged · Multi-VM · Real-Time*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)](https://postgresql.org)
[![Ollama](https://img.shields.io/badge/Ollama-0.6.6-white)](https://ollama.ai)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-108%20passing-brightgreen)](backend/tests/)

**[Live System](https://apts.marcbd.site) · [Interactive Docs](https://anis151993.github.io/pentai-pro/) · [Research Paper](docs/paper/pentai_ieee.tex)**

---

> **Copyright © 2026 Md Anisur Rahman Chowdhury. All rights reserved.**  
> Developed as part of Master's research — Department of Computer and Information Science, Gannon University, USA.

</div>

---

## Author

<div align="center">

### Md Anisur Rahman Chowdhury
**Master's of Information Technology**  
Department of Computer and Information Science, Gannon University, USA

[![Email](https://img.shields.io/badge/Email-engr.aanis@gmail.com-D14836?logo=gmail&logoColor=white)](mailto:engr.aanis@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?logo=linkedin&logoColor=white)](https://linkedin.com/in/md-anisur-rahman-chowdhury-15862420a)
[![GitHub](https://img.shields.io/badge/GitHub-ANIS151993-181717?logo=github&logoColor=white)](https://github.com/ANIS151993)
[![Google Scholar](https://img.shields.io/badge/Google_Scholar-Profile-4285F4?logo=google-scholar&logoColor=white)](https://scholar.google.com/citations?user=NQyywPoAAAAJ)
[![Portfolio](https://img.shields.io/badge/Portfolio-marcbd.site-FF5722?logo=firefox&logoColor=white)](https://marcbd.site)
[![ResearchGate](https://img.shields.io/badge/ResearchGate-Profile-00CCBB?logo=researchgate&logoColor=white)](https://researchgate.net/profile/Md-Anisur-Rahman-Chowdhury)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Key Features](#key-features)
4. [Hardware Requirements](#hardware-requirements)
5. [Infrastructure Setup](#infrastructure-setup)
6. [Step-by-Step Installation](#step-by-step-installation)
7. [AI Model Setup](#ai-model-setup)
8. [Supabase Self-Hosted Auth](#supabase-self-hosted-auth)
9. [Weapon Node Deployment](#weapon-node-deployment)
10. [Knowledge Base Ingestion](#knowledge-base-ingestion)
11. [Running the System](#running-the-system)
12. [Usage Guide](#usage-guide)
13. [Performance Results](#performance-results)
14. [Security Architecture](#security-architecture)
15. [API Reference](#api-reference)
16. [Development & Testing](#development--testing)
17. [Research Paper](#research-paper)
18. [License](#license)

---

## Overview

**PentAI Pro** is a production-grade, self-hosted automated penetration testing platform that orchestrates LLM-driven AI agents across isolated virtual machines. The system implements a full structured attack lifecycle — Reconnaissance → Enumeration → Vulnerability Mapping → Exploitation Planning — while enforcing three-layer scope validation, maintaining a tamper-evident SHA-256 hash-chained audit log, and requiring operator approval for all high-risk operations.

All components run **100% on-premises**: no cloud API keys, no external telemetry, no data leaving your infrastructure.

### What PentAI Pro Does

```
Operator defines scope (CIDR)
        │
        ▼
AI Agent classifies intent (recon_only / full_pentest / targeted_check)
        │
        ▼
Agent plans attack phases using KB-augmented LLM (RAG + qwen2.5:14b)
        │
        ▼
Tools execute on isolated Weapon Node via mTLS-secured gateway
        │
        ▼
Results parsed → Inventory built → Findings generated
        │
        ▼
Operator reviews, approves high-risk steps → Report exported
        │
        ▼
Every action recorded in tamper-evident audit chain
```

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      COMMAND NODE  172.20.32.74                        │
│                                                                        │
│  ┌─────────────┐   ┌───────────────┐   ┌───────────┐  ┌───────────┐  │
│  │  Next.js    │   │   FastAPI     │   │  Ollama   │  │ Supabase  │  │
│  │  Frontend   │◄──│   Backend     │──►│  :11434   │  │  :8543    │  │
│  │  :3000      │   │   :8000       │   │ qwen2.5   │  │ GoTrue    │  │
│  └──────┬──────┘   └──────┬────────┘   │ 14b / 3b  │  │ Auth      │  │
│         │                 │            │ embed-text │  └───────────┘  │
│    Caddy:80         ┌─────┴──────┐     └───────────┘                  │
│    reverse          │ PostgreSQL │                                     │
│    proxy            │   :5432    │                                     │
│                     └───────────┘                                     │
└─────────────────────────────┬──────────────────────────────────────────┘
                              │ mTLS + JWT  (port 5000)
┌─────────────────────────────▼──────────────────────────────────────────┐
│                      WEAPON NODE  172.20.32.68  (Kali Linux)           │
│                                                                        │
│       Flask Tool Gateway  (mutual TLS server)                          │
│       nmap │ httpx │ nuclei │ gobuster │ sslscan │ dnsx │ whatweb     │
└─────────────────────────────┬──────────────────────────────────────────┘
                              │  (isolated LAN)
┌─────────────────────────────▼──────────────────────────────────────────┐
│                      TARGET NODE  172.20.32.59                         │
│                      Isolated vulnerable test environment              │
└────────────────────────────────────────────────────────────────────────┘
```

### VM Map

| VM | ID | IP | Role | OS |
|----|----|----|------|-----|
| Command Node | 120 | 172.20.32.74 | Orchestration, UI, DB, LLM | Ubuntu 22.04 |
| Weapon Node | 123 | 172.20.32.68 | Tool execution | Kali Linux |
| Target Node | 122 | 172.20.32.59 | Test target | Configurable |

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Phase AI Agent** | Recon → Enum → Vulnerability Map → Exploit Plan — fully automated |
| **Local LLM (100% Offline)** | qwen2.5:14b for reasoning + llama3.2:3b for fast tasks via Ollama |
| **RAG Knowledge Base** | Vector search with nomic-embed-text — ingest custom playbooks |
| **Three-Layer Scope Guard** | CIDR enforcement at LLM planning, backend API, and weapon gateway |
| **Tamper-Evident Audit Log** | SHA-256 hash-chained event stream — cryptographically verifiable |
| **mTLS Node-to-Node** | Mutual TLS between Command ↔ Weapon Node — certificate-pinned |
| **Approval Workflows** | nuclei, gobuster, os_detection require explicit operator sign-off |
| **Real-Time Streaming** | Live tool output via WebSocket ExecutionBus + NDJSON |
| **Parser Enrichment** | nmap/nuclei/httpx auto-parsed into structured inventory + findings |
| **Self-Hosted Auth** | Supabase GoTrue on-premises — Supabase JWT validated by backend |
| **Structured Reports** | JSON artifact reports with findings, inventory, and audit evidence |

---

## Hardware Requirements

| Component | Minimum | This Build |
|-----------|---------|------------|
| RAM | 16 GB | **25 GB** |
| Storage | 100 GB | **400 GB** |
| CPU Cores | 4 | **6-core Intel Xeon Gold 6230** |
| GPU | — | Optional (accelerates LLM) |
| Network | LAN | Internal VLAN 172.20.32.0/18 |

### Disk Expansion (Proxmox / LVM)

If your root partition does not reflect the full disk size:

```bash
sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
df -h /   # confirm ~392 GB available
```

---

## Infrastructure Setup

### Step 1: Install Docker on Command Node

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Install Pentest Tools on Weapon Node (Kali)

```bash
sudo apt update && sudo apt install -y nmap nuclei gobuster whatweb sslscan

# Go-based tools
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
```

---

## Step-by-Step Installation

### 1. Clone Repository

```bash
git clone https://github.com/ANIS151993/pentai-pro.git
cd pentai-pro
```

### 2. Generate mTLS Certificates

```bash
chmod +x scripts/generate-certs.sh
./scripts/generate-certs.sh
ls certs/   # ca-cert.pem, command-client-cert.pem, command-client-key.pem
```

### 3. Create Root Environment File

```bash
cp .env.example .env
```

Set these values in `.env`:

```env
PENTAI_ALLOWED_NETWORK=172.20.32.0/18
PENTAI_COMMAND_NODE_IP=172.20.32.74
PENTAI_WEAPON_NODE_URL=https://172.20.32.68:5000
PENTAI_POSTGRES_DSN=postgresql+psycopg://pentai:pentai@postgres:5432/pentai
PENTAI_AUTH_JWT_SECRET=<openssl rand -hex 32>
PENTAI_GATEWAY_JWT_SECRET=<openssl rand -hex 32>
PENTAI_SUPABASE_JWT_SECRET=<matches supabase JWT_SECRET>
PENTAI_CORS_ALLOW_ORIGINS=http://172.20.32.74:3000
```

### 4. Build and Start Services

```bash
docker compose build backend frontend
docker compose up -d
docker compose ps   # all services healthy
```

### 5. Verify Health

```bash
curl http://172.20.32.74/api/v1/healthz
# {"status":"ok","database_status":"ok","ollama_status":"ok","ollama_models":[...]}
```

---

## AI Model Setup

```bash
# Main reasoning model — planning, vulnerability analysis, findings (9 GB)
docker exec pentai-pro-ollama-1 ollama pull qwen2.5:14b-instruct-q4_K_M

# Fast classification model — intent classify, tool output parse (2 GB)
docker exec pentai-pro-ollama-1 ollama pull llama3.2:3b-instruct-q4_K_M

# Embedding model — knowledge base RAG (274 MB)
docker exec pentai-pro-ollama-1 ollama pull nomic-embed-text

# Verify
docker exec pentai-pro-ollama-1 ollama list
```

### Model Performance (CPU — Intel Xeon Gold 6230 @ 2.10 GHz)

| Model | RAM | Speed | Role |
|-------|-----|-------|------|
| qwen2.5:14b-q4_K_M | ~9 GB | ~12 tok/s | Planning, reasoning, findings |
| llama3.2:3b-q4_K_M | ~2 GB | ~45 tok/s | Classification, parsing |
| nomic-embed-text | ~274 MB | ~200 emb/s | Vector embeddings |

---

## Supabase Self-Hosted Auth

```bash
git clone https://github.com/supabase/supabase.git ~/supabase-docker
cd ~/supabase-docker/docker
cp .env.example .env
```

Key settings in `.env`:

```env
JWT_SECRET=<openssl rand -hex 64>
KONG_HTTP_PORT=8543
STUDIO_PORT=3001
ENABLE_EMAIL_AUTOCONFIRM=true
DOCKER_SOCKET_LOCATION=/var/run/docker.sock
SITE_URL=http://172.20.32.74
```

```bash
docker compose up -d
docker compose ps   # 13 containers healthy

# Verify GoTrue
curl http://172.20.32.74:8543/auth/v1/health \
  -H "apikey: <ANON_KEY>"
```

Configure frontend `.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=http://172.20.32.74:8543
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
NEXT_PUBLIC_API_BASE_URL=http://172.20.32.74:8000
```

Rebuild frontend to bake in env vars:

```bash
cd pentai-pro && docker compose up -d --build frontend
```

---

## Weapon Node Deployment

```bash
# From Command Node
chmod +x scripts/setup-weapon-node.sh
./scripts/setup-weapon-node.sh

# Verify mTLS handshake
python scripts/mtls_smoke.py
```

---

## Knowledge Base Ingestion

```bash
# Ingest a markdown knowledge document
python scripts/ingest_kb.py --file playbooks/web-app-recon.md

# List ingested sources
curl http://172.20.32.74/api/v1/knowledge/sources \
  -H "Authorization: Bearer <token>"

# Semantic search
curl -X POST http://172.20.32.74/api/v1/knowledge/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "CVE-2021-44228 detection"}'
```

---

## Running the System

### Access Points

| Service | URL | Notes |
|---------|-----|-------|
| PentAI Pro | `http://172.20.32.74` | Main application |
| Supabase Studio | `http://172.20.32.74:3001` | admin / dashboard password |
| API Swagger Docs | `http://172.20.32.74/docs` | Bearer token required |
| Live System | `https://apts.marcbd.site` | Public demo |

---

## Usage Guide

### 1. Create Engagement
Go to `/engagements/new` → Enter name + scope CIDR (e.g. `172.20.32.59/32`) + confirm authorization.

### 2. Run AI Agent
Go to `/engagements/{id}/agent` → Type goal → Agent runs full pipeline:
```
classify_intent → plan_recon → call_tools → plan_enumeration → map_vulnerabilities → plan_exploitation
```

### 3. Approve High-Risk Tools
Go to `/engagements/{id}/console` → Approvals Queue → Review args → Approve or Reject.

### 4. Generate Report
```bash
POST /api/v1/engagements/{id}/reports
```
Returns JSON with findings, inventory, agent steps, and audit chain.

---

## Performance Results

> Full interactive charts: **[https://anis151993.github.io/pentai-pro/](https://anis151993.github.io/pentai-pro/)**

| Metric | Value |
|--------|-------|
| Recon planning latency | 18.4 s avg |
| Tool execution (nmap service scan) | 42.1 s avg |
| Finding generation | 11.2 s avg |
| KB retrieval latency | 0.8 s |
| WebSocket event delay | < 50 ms |
| Scope check overhead | < 5 ms |
| Audit chain validation (100 events) | < 200 ms |
| Test suite (108 tests) | 43.5 s |
| Backend memory | ~380 MB |
| LLM throughput (14b, CPU) | ~12 tok/s |

---

## Security Architecture

### Three-Layer Scope Enforcement

```
Layer 1 — LLM Planning
  All targets validated against scope_cidrs before any tool is proposed

Layer 2 — Backend API  (core/scope.py + core/gateway_validation.py)
  CIDR check + approval status verified before JWT issued to Weapon Node

Layer 3 — Weapon Node Gateway  (tool-gateway/gateway/auth.py)
  Scope re-validated on arrival + JWT signature + audience verified
```

### Tamper-Evident Audit Log

```python
# core/audit.py — SHA-256 hash chaining
hash[n] = SHA256(JSON({
    "event_type": ...,
    "payload": ...,
    "prev_hash": hash[n-1],   # genesis = "0" * 64
    "timestamp": utcnow(),
}))
```

### mTLS Architecture

```
Lab CA  →  Command Node client cert  →  authenticates to Weapon Node server cert
```

---

## API Reference

All endpoints at `/api/v1`. Interactive docs at `/docs`.

```
GET  /healthz                               System health + model list
POST /auth/login                            Authenticate (email + password)
GET  /auth/me                               Current user
GET  /engagements                           List all engagements
POST /engagements                           Create engagement
POST /engagements/{id}/approvals            Request high-risk tool approval
PATCH /approvals/{id}                       Decide approval (approve/reject)
GET  /engagements/{id}/tool-executions      Execution history
GET  /engagements/{id}/inventory            Parsed hosts + services
POST /engagements/{id}/reports              Generate report
GET  /engagements/{id}/audit-events         Tamper-evident audit chain
POST /knowledge/sources                     Ingest KB document
POST /knowledge/search                      Semantic vector search
WS   /ws/executions/{id}?ticket=...         Stream live execution events
```

---

## Development & Testing

```bash
cd backend

# Install dev dependencies
uv pip install -e ".[dev]"

# Run full test suite
.venv/bin/python -m pytest tests/ -v
# 108 passed in 43.5 s

# Run specific module
.venv/bin/python -m pytest tests/api/test_auth.py -v
```

---

## Research Paper

A peer-reviewed IEEE conference paper describing the design, implementation, and evaluation of PentAI Pro:

**[docs/paper/pentai_ieee.tex](docs/paper/pentai_ieee.tex)**

> *Md Anisur Rahman Chowdhury, Dr. Ronny Bazan-Antequera*  
> *Department of Computer and Information Science, Gannon University, USA*

---

## License

MIT License

Copyright © 2024–2025 **Md Anisur Rahman Chowdhury**

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

---

<div align="center">

**Developed by Md Anisur Rahman Chowdhury**  
Master's of Information Technology · Gannon University · Erie, PA, USA

[marcbd.site](https://marcbd.site) · [GitHub](https://github.com/ANIS151993) · [LinkedIn](https://linkedin.com/in/md-anisur-rahman-chowdhury-15862420a) · [Google Scholar](https://scholar.google.com/citations?user=NQyywPoAAAAJ) · [ResearchGate](https://researchgate.net/profile/Md-Anisur-Rahman-Chowdhury)

</div>
