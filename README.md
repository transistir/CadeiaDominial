# 🏡 CadeiaDominial

[![CI](https://img.shields.io/github/actions/workflow/status/transistir/CadeiaDominial/ci.yml?style=flat-square&label=CI)](https://github.com/transistir/CadeiaDominial/actions)
[![Coverage](https://img.shields.io/codecov/c/github/transistir/CadeiaDominial?style=flat-square)](https://codecov.io/gh/transistir/CadeiaDominial)
[![Sentry](https://img.shields.io/badge/sentry-monitoring-%237E1FFF?logo=sentry&logoColor=white&style=flat-square)](https://sentry.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Full-stack TypeScript monorepo powered by Cloudflare Workers, React + Vite, Hono, and Drizzle — designed for land registry exploration.

## 📖 Project Overview

**Cadeia Dominial** (Chain of Title) is a web system for managing and visualizing property ownership chains for indigenous lands in Brazil. The system enables authorized users to:

- 📋 **Manage Properties**: Track indigenous lands (TIs), properties, and documents
- 🏢 **Notary Offices**: Comprehensive database of Brazilian cartórios
- 🌳 **Interactive Tree Visualization**: Visual exploration of property chains with zoom/pan
- 👥 **Multi-User Support**: Role-based access (admin, editor, viewer)

This is a **modern TypeScript rewrite** of the original Django application, leveraging Cloudflare's edge platform for global performance and scalability.

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🚀 Tech Stack](#-tech-stack)
- [💻 Getting Started](#-getting-started)
- [⚙️ Development](#-development)
  - [Running Locally](#running-locally)
  - [Database Migrations](#database-migrations)
  - [Claude Code Integration](#claude-code-integration)
- [🔐 Authentication](#-authentication)
- [🗄️ Database](#-database)
- [📦 Deployment](#-deployment)
- [🎯 Roles & Permissions](#-roles--permissions)
- [📄 License](#-license)

---

## ✨ Features

- 🌍 Edge-first deployment with Cloudflare Pages + Workers
- 🔐 JWT authentication with Hono middleware
- ⚡ Instant hot-reload dev with Vite + React
- 🧩 End-to-end type safety with Zod validation
- 🗄️ Cloudflare D1 (SQLite) with Drizzle ORM
- 🧪 Testing with Vitest + Playwright + Codecov
- 🧹 Code style enforced with ESLint + Prettier
- 🎯 Role-based access (admin, editor, viewer)
- 📈 Observability with Sentry and CI/CD on GitHub Actions

---

## 🚀 Tech Stack

| Layer          | Tooling                                      |
| -------------- | -------------------------------------------- |
| **Frontend**   | React, Vite, TanStack Router/Query, Tailwind |
| **Backend**    | Hono, Drizzle ORM, SQLite (D1)               |
| **Auth**       | Hono JWT + D1                                |
| **Infra**      | Cloudflare Workers + Pages + D1              |
| **Tooling**    | TypeScript, Vitest, Playwright, ESLint       |
| **CI/CD**      | GitHub Actions, Wrangler, Codecov            |
| **Monitoring** | Sentry                                       |

---

## 💻 Getting Started

### Prerequisites

- Node.js v20+ (LTS)
- pnpm (`npm i -g pnpm`)
- Wrangler CLI (`npm i -g wrangler`)
- Cloudflare account (for D1 + Pages)

### Installation

```bash
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial
pnpm install
cp packages/api/.dev.vars.example packages/api/.dev.vars
cp packages/web/.env.example packages/web/.env
```

### Run Dev Environment

```bash
pnpm dev   # Starts both frontend and API
```

---

## ⚙️ Development

### Running Locally

```bash
# Full monorepo (recommended)
pnpm dev

# Or individually:
cd packages/web && pnpm dev   # Frontend at http://localhost:5173
cd packages/api && pnpm dev   # API at http://localhost:8787
```

The web dev server proxies `/api` to `http://localhost:8787`. By default the app
uses `/api` as `VITE_API_BASE_URL`, so local dev does not need any env overrides.
Only set a full URL in `packages/web/.env` when you want to bypass the proxy
(preview or a remote API).

For production and preview builds, set `VITE_API_BASE_URL` to the deployed API
URL (for example, the Workers URL) via your Pages environment configuration.

**Local ports**
- Web: `http://localhost:5173`
- API: `http://localhost:8787`

### Database Migrations

```bash
pnpm db:generate       # Generate migrations from schema
pnpm db:migrate:local  # Apply to local D1
```

If you haven't created the D1 database yet (remote, one-time):

```bash
wrangler d1 create cadeia-dominial --config packages/api/wrangler.toml
```

For the simplest local/remote workflow, see `docs/D1_LOCAL_DEV.md`.
For quick commands, see `docs/DEPLOYMENT.md` (D1 cheat sheet).

### Claude Code Integration

This project includes **Agent-Driven Development (ADD)** workflow via `.claude/` configuration.

#### Quick Start

```bash
# Initialize workflow for an issue
/init <issue-id> <sub-id>

# Execute phases (creates artifacts in .project/issues/)
/research    # Codebase analysis
/spec        # Write specification
/tests       # Design tests
/plan        # Implementation plan
/dev         # Implement code
/qa          # Quality assurance

# Check status
/status
```

#### Workflow

```
Issue → Context → Research → Spec → Tests → Plan → Dev → QA → Complete
         ↓          ↓         ↓       ↓       ↓     ↓    ↓       ↓
      (commit)   (commit)  (commit) (commit) (commit) (auto) (commit)
```

#### Artifacts

Each phase creates an artifact in `.project/issues/ISSUE-{id}/`:

| Phase    | Artifact       | Description                            |
| -------- | -------------- | -------------------------------------- |
| context  | 00-context.md  | Scope and boundaries                   |
| research | 01-research.md | Codebase analysis                      |
| spec     | 02-spec.md     | Specification with acceptance criteria |
| tests    | 03-tests.md    | Test specification                     |
| plan     | 04-plan.md     | Implementation plan                    |
| qa       | 05-qa-agent.md | QA report                              |

**Approval**: Commit artifact to git = phase approved.

If you have the Claude Code config installed locally, see `.claude/skills/add-workflow.md` for full documentation.

---

## 🔐 Authentication

- JWT-based auth via **Hono middleware**
- User data stored in **D1**
- Roles stored in the user table: `admin`, `editor`, `viewer`
- Role enforcement via custom Hono middleware

---

## 🗄️ Database

- **Cloudflare D1** (SQLite)
- Accessed via **Drizzle ORM**
- Migrations tracked with `drizzle-kit`
- Admin UI via **Drizzle Studio** at `/admin`

---

## 📦 Deployment

- Frontend: **Cloudflare Pages**
- API: **Cloudflare Workers** via Wrangler
- CI: GitHub Actions
  - Lint + Typecheck
  - Tests + Coverage (Codecov)
  - Auto-deploy on push to `main`

---

## 🎯 Roles & Permissions

| Role   | Description      |
| ------ | ---------------- |
| Admin  | Full access      |
| Editor | Add/edit records |
| Viewer | Read-only access |

---

## 📄 License

MIT © [transistir](https://github.com/transistir)
