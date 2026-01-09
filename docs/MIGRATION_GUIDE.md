# 📘 CadeiaDominial Migration Guide (Full TypeScript Stack)

This guide outlines our migration from a Django monolith to a modern full-stack TypeScript architecture using **React + Vite** (frontend), **Hono** (backend API), and **Drizzle** (ORM) on the Cloudflare platform.

---

## Migration Context

### What We're Migrating From

The current **Cadeia Dominial** system is a Django 5.2.3 application:

| Aspect            | Current (Django)                 | Target (TypeScript)              |
| ----------------- | -------------------------------- | -------------------------------- |
| **Backend**       | Django 5.2.3, Python 3.8+        | Hono on Cloudflare Workers       |
| **Frontend**      | Django Templates + Vanilla JS    | React + Vite on Cloudflare Pages |
| **Database**      | PostgreSQL (prod) / SQLite (dev) | Cloudflare D1 (SQLite)           |
| **Auth**          | Django Auth System               | Hono JWT + D1                    |
| **Deployment**    | Traditional server               | Cloudflare Pages + Workers       |
| **Visualization** | D3.js tree                       | React-based visualization        |

### Core Features to Preserve

- **Interactive Tree Visualization**: Property chain visualization with zoom/pan
- **Data Management**: Indigenous lands (TIs), properties, documents, notary offices
- **Role-Based Access**: Admin, editor, viewer permissions
- **Duplicate Detection**: Automatic prevention of duplicate data
- **Data Export**: Excel, PDF, JSON export capabilities

### Migration Goals

- **Full-Stack TypeScript**: Type safety across frontend and backend
- **Edge-First Deployment**: Global performance via Cloudflare Workers
- **Modern Developer Experience**: Instant HMR with Vite, fast builds
- **Cost Efficiency**: Serverless architecture reduces infrastructure costs
- **Scalability**: Auto-scaling edge deployment
- **Architectural Clarity**: Clean separation between frontend and API

---

## 1. 📐 Architecture Decisions

### Frontend Framework: React + Vite

**Decision**: Use **React 19+** with **Vite** and **TanStack Router**.

**Rationale**:

- ✅ Instant HMR for rapid development
- ✅ Minimal bundle size—leaves headroom for visualization libraries
- ✅ Clean separation from backend API
- ✅ Modern React with concurrent features
- ✅ Static deployment on Cloudflare Pages (free for static assets)

> **Reference**: [ADR-001 in ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md)

### Backend API: Hono on Cloudflare Workers

**Decision**: Use **Hono** as the backend framework on Workers.

**Rationale**:

- ✅ Ultra-light (~14KB bundle)
- ✅ Native D1 bindings—no adapter overhead
- ✅ Best-in-class edge performance (<50ms cold start)
- ✅ Excellent TypeScript support with full inference
- ✅ Clean middleware architecture

> **Reference**: [ADR-002 in ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md)

### Authentication: Hono JWT + D1

**Decision**: Use **Hono's JWT middleware** with D1 for user storage.

**Rationale**:

- ✅ Minimal bundle size (~2KB)
- ✅ Full control over auth flow
- ✅ Direct D1 queries—no adapter overhead
- ✅ Simple to understand and debug
- ✅ Migration path to Lucia Auth if OAuth needed later

> **Reference**: [ADR-004 in ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md)

---

## 2. 🗂 Directory Structure

```txt
/
├── packages/
│   ├── web/                      # React + Vite frontend
│   │   ├── src/
│   │   │   ├── components/       # Reusable UI components (shadcn/ui)
│   │   │   ├── features/         # Feature modules
│   │   │   │   ├── auth/         # Login, logout, auth context
│   │   │   │   ├── tis/          # Indigenous lands management
│   │   │   │   ├── properties/   # Property management
│   │   │   │   ├── documents/    # Document management
│   │   │   │   ├── tree/         # Hierarchy visualization
│   │   │   │   └── export/       # Export functionality
│   │   │   ├── lib/              # Utilities, API client
│   │   │   ├── routes/           # TanStack Router routes
│   │   │   └── styles/           # Global styles, Tailwind
│   │   ├── public/               # Static assets
│   │   ├── vite.config.ts
│   │   └── package.json
│   │
│   ├── api/                      # Hono backend on Workers
│   │   ├── src/
│   │   │   ├── routes/           # API route handlers
│   │   │   ├── services/         # Business logic
│   │   │   ├── middleware/       # Auth, logging, validation
│   │   │   └── index.ts          # Hono app entry point
│   │   ├── drizzle/
│   │   │   ├── schema.ts         # Drizzle schema definitions
│   │   │   └── migrations/       # SQL migrations
│   │   ├── wrangler.toml         # Cloudflare Workers config
│   │   └── package.json
│   │
│   └── shared/                   # Shared types and schemas
│       └── src/
│           ├── types/            # TypeScript interfaces
│           └── schemas/          # Zod validation schemas
│
├── tests/                        # Vitest + Playwright tests
├── .github/workflows/            # CI/CD
├── turbo.json                    # Turborepo configuration
├── package.json                  # Workspace root
└── README.md
```

---

## 3. 🧱 Tech Stack Details

### Frontend (packages/web)

| Library             | Purpose                 | Version |
| ------------------- | ----------------------- | ------- |
| **React**           | UI framework            | 19+     |
| **Vite**            | Build tool              | 6+      |
| **TanStack Router** | Type-safe routing       | 1.x     |
| **TanStack Query**  | Server state management | 5.x     |
| **Tailwind CSS**    | Utility-first styling   | 3.x     |
| **shadcn/ui**       | Component library       | latest  |
| **Zod**             | Runtime validation      | 3.x     |

### Backend (packages/api)

| Library                 | Purpose            | Version |
| ----------------------- | ------------------ | ------- |
| **Hono**                | Web framework      | 4.x     |
| **Drizzle ORM**         | Type-safe SQL      | 0.30+   |
| **Zod**                 | Request validation | 3.x     |
| **@hono/zod-validator** | Zod integration    | latest  |
| **bcryptjs**            | Password hashing   | 2.x     |

### Database

- **Cloudflare D1**: SQLite at the edge
- **Drizzle ORM**: Type-safe SQL
- **Drizzle Kit**: Migration management

### Tooling

| Tool           | Purpose                   |
| -------------- | ------------------------- |
| **Turborepo**  | Monorepo management       |
| **TypeScript** | Type safety (strict mode) |
| **ESLint**     | Code quality              |
| **Prettier**   | Code formatting           |
| **Vitest**     | Unit testing              |
| **Playwright** | E2E testing               |
| **Wrangler**   | Cloudflare CLI            |

---

## 4. 🔐 Authentication Architecture

### Hono JWT + D1

Authentication is implemented using Hono's built-in JWT middleware with user data stored in D1.

```typescript
// api/src/routes/auth.ts
import { Hono } from "hono";
import { sign } from "hono/jwt";
import { zValidator } from "@hono/zod-validator";
import { z } from "zod";
import bcrypt from "bcryptjs";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type Bindings = { DB: D1Database; JWT_SECRET: string };

export const authRoutes = new Hono<{ Bindings: Bindings }>();

authRoutes.post("/login", zValidator("json", loginSchema), async (c) => {
  const { email, password } = c.req.valid("json");

  const user = await c.env.DB.prepare("SELECT * FROM users WHERE email = ?")
    .bind(email)
    .first();

  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return c.json({ error: "Invalid credentials" }, 401);
  }

  const token = await sign(
    {
      sub: user.id,
      role: user.role,
      exp: Math.floor(Date.now() / 1000) + 86400,
    },
    c.env.JWT_SECRET,
  );

  return c.json({
    token,
    user: { id: user.id, email: user.email, role: user.role },
  });
});
```

### Role-Based Access Control

```typescript
// api/src/middleware/auth.ts
import { jwt } from "hono/jwt";
import { HTTPException } from "hono/http-exception";

// JWT validation middleware
export const jwtMiddleware = jwt({ secret: (c) => c.env.JWT_SECRET });

// Role-based access middleware
export const requireRole = (...roles: string[]) => {
  return async (c, next) => {
    const payload = c.get("jwtPayload");
    if (!payload) throw new HTTPException(401, { message: "Unauthorized" });
    if (!roles.includes(payload.role))
      throw new HTTPException(403, { message: "Forbidden" });
    await next();
  };
};

// Usage in main app
app.use("/api/*", jwtMiddleware);
app.use("/api/admin/*", requireRole("admin"));
app.use("/api/edit/*", requireRole("admin", "editor"));
```

### Frontend Auth Context

```typescript
// web/src/features/auth/auth-context.tsx
import { createContext, useContext, useState, useEffect } from 'react'

interface AuthContextType {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))

  async function login(email: string, password: string) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })
    if (!res.ok) throw new Error('Invalid credentials')
    const { token, user } = await res.json()
    localStorage.setItem('token', token)
    setToken(token)
    setUser(user)
  }

  function logout() {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
```

---

## 5. 💻 Local Development Setup

### Prerequisites

```bash
# Node.js v20+ (LTS recommended)
node --version  # Should be v20+

# pnpm (package manager)
npm install -g pnpm

# Wrangler CLI
npm install -g wrangler

# Cloudflare account (free tier works)
# Sign up at: https://dash.cloudflare.com/sign-up
```

### Installation

```bash
# Clone repository
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Install dependencies (uses pnpm workspaces)
pnpm install

# Copy environment templates
cp packages/api/.dev.vars.example packages/api/.dev.vars
cp packages/web/.env.example packages/web/.env
```

### Environment Variables

**API (packages/api/.dev.vars)**:

```bash
# JWT authentication
JWT_KEY="generate-with-openssl-rand-base64-32"

# Database binding handled by wrangler.toml
```

**Frontend (packages/web/.env)**:

```bash
# API endpoint (dev only, proxied by Vite)
VITE_API_URL="http://localhost:8787"

# Monitoring (optional)
VITE_SENTRY_DSN=""
```

### Start Development

```bash
# From root directory - starts both frontend and API
pnpm dev

# Or run individually:
# Terminal 1: API (Hono on Workers)
cd packages/api && pnpm dev

# Terminal 2: Frontend (Vite)
cd packages/web && pnpm dev

# Frontend: http://localhost:5173
# API: http://localhost:8787
```

### Database Setup

```bash
cd packages/api

# Create local D1 database
npx wrangler d1 create cadeiadominial-db --local

# Generate migrations from Drizzle schema
pnpm db:generate

# Apply migrations locally
pnpm db:migrate:local

# Open Drizzle Studio for inspection
pnpm db:studio
```

---

## 6. 🚀 Deployment

### Deploy API (Workers)

```bash
cd packages/api

# Create production D1 database
npx wrangler d1 create cadeiadominial-db

# Run migrations on production
pnpm db:migrate:prod

# Deploy to Workers
npx wrangler deploy
```

### Deploy Frontend (Pages)

```bash
cd packages/web

# Build and deploy
pnpm build
npx wrangler pages deploy dist --project-name=cadeiadominial
```

### Configuration Files

**API wrangler.toml**:

```toml
name = "cadeiadominial-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

[[d1_databases]]
binding = "DB"
database_name = "cadeiadominial-db"
database_id = "your-database-id-here"
```

**Web vite.config.ts**:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: { "/api": { target: "http://localhost:8787", changeOrigin: true } },
  },
});
```

---

## 7. 📋 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: 8
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test:unit
      - run: pnpm build

  deploy-api:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy API
        uses: cloudflare/wrangler-action@v3
        with:
          workingDirectory: packages/api

  deploy-web:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Pages
        uses: cloudflare/pages-action@v1
        with:
          projectName: cadeiadominial
          directory: packages/web/dist
```

---

## 8. 📊 Monitoring & Observability

### Error Tracking (Sentry)

```typescript
// web/src/main.tsx
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  tracesSampleRate: 0.1,
});
```

### Performance Monitoring

- **Web Vitals**: Vite plugin for Core Web Vitals
- **Cloudflare Analytics**: Automatic with Workers/Pages
- **Hono Logging**: Built-in request timing middleware

---

## 9. 🧰 Development Standards

### Code Quality

- **Linting**: ESLint with TypeScript rules
- **Formatting**: Prettier with consistent config
- **Type Safety**: Strict TypeScript, no `any`
- **Testing**: Minimum 80% coverage

### Git Workflow

```bash
# Feature branch workflow
git checkout -b feature/feature-name
# ... make changes ...
git commit -m "feat: add feature description"
git push origin feature/feature-name
# Create pull request
```

### Commit Convention (Conventional Commits)

```
feat: add new feature
fix: bug fix
docs: documentation changes
style: code style changes
refactor: code refactoring
test: adding or updating tests
chore: maintenance tasks
```

---

## Sources & References

### Hono Framework

- [Hono Documentation](https://hono.dev/docs)
- [Hono JWT Middleware](https://hono.dev/docs/middleware/builtin/jwt)
- [Hono on Cloudflare Workers](https://hono.dev/docs/getting-started/cloudflare-workers)
- [Hono Best Practices](https://hono.dev/docs/guides/best-practices)
- [Hono Zod Validator](https://hono.dev/docs/guides/validation#with-zod)

### Vite + React

- [Vite Documentation](https://vitejs.dev/guide/)
- [TanStack Router](https://tanstack.com/router/latest)
- [TanStack Query](https://tanstack.com/query/latest)
- [Vite on Cloudflare Pages](https://developers.cloudflare.com/pages/framework-guides/deploy-a-vite3-project/)

### Cloudflare Platform

- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers/)
- [Cloudflare Pages Documentation](https://developers.cloudflare.com/pages/)
- [Cloudflare Pages Functions](https://developers.cloudflare.com/pages/functions/)

### D1 Database

- [D1 Documentation](https://developers.cloudflare.com/d1/)
- [D1 Best Practices](https://developers.cloudflare.com/d1/best-practices/)
- [D1 Local Development Guide](https://developers.cloudflare.com/d1/best-practices/local-development/)

### Drizzle ORM

- [Drizzle ORM Documentation](https://orm.drizzle.team/docs/overview)
- [Drizzle with D1](https://orm.drizzle.team/docs/get-started-sqlite#cloudflare-d1)

---

**Last Updated**: 2026-01-08
**Version**: 2.0.0
