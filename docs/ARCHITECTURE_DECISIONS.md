# 🏗️ Architecture Decisions Record

This document records significant architectural decisions made for the CadeiaDominial migration, along with their context, consequences, and current status.

---

## ADR-001: Frontend Framework - React + Vite + Hono

**Status**: ✅ **DECIDED** - React + Vite (Frontend) + Hono (Backend)
**Date**: 2026-01-08
**Decision Maker**: Development Team
**Supersedes**: Previous decision for Next.js (2025-01-08)

### Context

The project needs to migrate from Django templates to a modern React-based frontend. The decision was revisited in January 2026 due to significant changes in Cloudflare's architecture and ecosystem learnings.

**Key factors evaluated:**

1. SEO requirements → **Not critical** (internal/professional users)
2. SSR benefits → **Nice-to-have** but not essential
3. Development approach → **AI-assisted coding** (agents familiar with both stacks)
4. Architecture preference → **Convention-driven** (team has no strong opinions)

### Decision

**Choose React + Vite + Hono** as a separated frontend/backend monorepo architecture.

### Rationale (2026 Update)

| Factor                 | Next.js                              | React + Vite + Hono      | Winner for CadeiaDominial |
| ---------------------- | ------------------------------------ | ------------------------ | ------------------------- |
| **Bundle Size**        | ⚠️ 1-3MB on Workers (limit concerns) | ✅ Minimal overhead      | **Vite + Hono**           |
| **Build Speed**        | ⚠️ Slower HMR                        | ✅ Sub-second HMR        | **Vite + Hono**           |
| **SEO**                | ✅ Built-in SSR/SSG                  | ⚠️ SPA (not needed here) | Tie (SEO not required)    |
| **Deployment**         | ⚠️ Complex on Workers                | ✅ Clean separation      | **Vite + Hono**           |
| **Architecture**       | ⚠️ Framework overhead                | ✅ Full control          | **Vite + Hono**           |
| **D1 Integration**     | ✅ NextAuth adapter                  | ✅ Direct Hono + D1      | Tie                       |
| **Tree Visualization** | ⚠️ Bundle size pressure              | ✅ More headroom         | **Vite + Hono**           |
| **Convention**         | ✅ Opinionated                       | ✅ Monorepo conventions  | Tie                       |

#### Why the Change from Next.js?

1. **Cloudflare Workers Bundle Limits**: Tree visualization (D3.js/React Flow) + auth + forms can push Next.js past comfortable 1-3MB limits on Workers
2. **2025 Cloudflare Evolution**: Workers became the default platform; Pages is now the beginner onramp. Clean API separation aligns better with this model
3. **SEO Not Required**: CadeiaDominial serves legal professionals and registrars—internal tool patterns, not public discovery
4. **Development Speed**: Vite's instant HMR significantly improves iteration speed for AI-assisted development
5. **Architectural Clarity**: Chain-of-title systems require auditable, testable code—clean frontend/backend separation aids this

#### Specific to CadeiaDominial

1. **Bundle Size Headroom**: D3.js/React Flow for tree visualization needs space; Vite + Hono stays well under limits
2. **Legal Domain Requirements**: Clear separation aids auditing and compliance verification
3. **AI-Assisted Development**: Both Vite and Hono have excellent TypeScript support; agents work effectively with both
4. **Document Management**: Separate API makes file upload/R2 integration cleaner

### Consequences

#### Positive

- ✅ Maximum control over architecture and conventions
- ✅ Minimal bundle size—well under Workers limits even with visualization libraries
- ✅ Instant HMR for rapid development iteration
- ✅ Clean API contract between frontend and backend
- ✅ Easier to test, audit, and maintain separately
- ✅ Cost-effective: static assets free on Pages, only API compute billed
- ✅ Future-proof: can scale API independently if needed

#### Negative

- ❌ Two deployment targets (frontend on Pages, API on Workers)
- ❌ Manual CORS and authentication token flow coordination
- ❌ No built-in SSR (acceptable since SEO not required)
- ❌ Requires establishing monorepo conventions

### Mitigations

| Concern                  | Mitigation                                                           |
| ------------------------ | -------------------------------------------------------------------- |
| Two deployments          | Single `wrangler` command deploys both; CI/CD handles coordination   |
| CORS/Auth coordination   | Shared types package; Zod schemas for validation                     |
| No SSR                   | Client-side rendering sufficient; can add `vite-ssg` later if needed |
| Convention establishment | Turborepo structure with clear package boundaries                    |

### Architecture Overview

```
cadeia-dominial/
├── packages/
│   ├── web/                    # React + Vite + TanStack Router
│   │   ├── src/
│   │   │   ├── components/     # UI components (shadcn/ui)
│   │   │   ├── features/       # Feature modules
│   │   │   │   ├── tree/       # Hierarchy visualization
│   │   │   │   ├── documents/  # Document management
│   │   │   │   └── search/     # Property search
│   │   │   └── lib/            # API client, utilities
│   │   └── vite.config.ts
│   │
│   ├── api/                    # Hono on Workers
│   │   ├── src/
│   │   │   ├── routes/         # API routes
│   │   │   ├── services/       # Business logic
│   │   │   └── middleware/     # Auth, logging, validation
│   │   └── wrangler.toml
│   │
│   └── shared/                 # Shared types, validation schemas
│       └── src/
│           ├── types/          # TypeScript interfaces
│           └── schemas/        # Zod schemas (shared validation)
│
├── turbo.json                  # Monorepo orchestration
└── package.json
```

### Alternatives Considered

1. **Next.js on Cloudflare Workers**
   - Bundle size concerns with tree visualization
   - More complex deployment configuration
   - SSR benefits not needed for this use case

2. **Astro + Hono**
   - Excellent for content-heavy sites
   - Overkill for application-focused system
   - Less React ecosystem integration

3. **Remix on Cloudflare**
   - Good Cloudflare integration
   - Similar bundle concerns as Next.js
   - Smaller community

### References

- [Cloudflare Full-Stack Development on Workers (2025)](https://blog.cloudflare.com/full-stack-development-on-cloudflare-workers/)
- [Hono vs Express vs Fastify: 2025 Architecture Guide](https://levelup.gitconnected.com/hono-vs-express-vs-fastify-the-2025-architecture-guide-for-next-js-5a13f6e12766)
- [From Next.js Route Handler to Hono](https://dev.to/pipipi-dev/from-nextjs-route-handler-to-hono-why-api-design-got-easier-3jo1)
- [Why We Migrated from Next.js to Vite and Hono](https://www.pluslide.com/blog/nextjs-to-vite-migration/)
- [Workers vs Pages (Reddit Discussion)](https://www.reddit.com/r/CloudFlare/comments/1ip87mx/workers_vs_pages/)

---

## ADR-002: Backend API - Hono on Cloudflare Workers

**Status**: ✅ **DECIDED** - Hono
**Date**: 2026-01-08
**Decision Maker**: Development Team
**Supersedes**: Previous tentative decision for Next.js API Routes (2025-01-08)

### Context

With the decision to use React + Vite for the frontend (ADR-001), the backend API framework becomes a standalone choice. Hono is the clear winner for Cloudflare Workers.

### Decision

**Use Hono** as the primary backend API framework on Cloudflare Workers.

### Rationale

| Factor               | Hono               | Express/Fastify    | Next.js Routes        |
| -------------------- | ------------------ | ------------------ | --------------------- |
| **Edge Performance** | ✅ Excellent       | ❌ Not edge-native | ⚠️ Good               |
| **Bundle Size**      | ✅ ~14KB           | ❌ Large           | ⚠️ Framework overhead |
| **Cold Start**       | ✅ <50ms           | ❌ >200ms          | ⚠️ Variable           |
| **D1 Integration**   | ✅ Native bindings | ⚠️ Adapter needed  | ⚠️ Adapter needed     |
| **TypeScript**       | ✅ First-class     | ⚠️ Added           | ✅ Native             |
| **Middleware**       | ✅ Elegant         | ✅ Mature          | ⚠️ Limited            |
| **Workers Compat**   | ✅ Built for it    | ❌ Node.js focused | ⚠️ Partial            |

#### Hono Advantages for CadeiaDominial

1. **Ultra-Light**: ~14KB bundle, leaving headroom for business logic
2. **Native D1 Bindings**: Direct database access without adapters
3. **Type-Safe Routes**: Full TypeScript inference on routes, params, and responses
4. **Middleware Ecosystem**: Auth, CORS, validation, logging—all optimized for edge
5. **Multi-Runtime**: Works on Workers, Deno, Bun, Node if migration needed

### Authentication Strategy

With Hono (instead of NextAuth.js), authentication options:

**Option A: Hono + JWT + D1** (Recommended)

```typescript
// api/src/middleware/auth.ts
import { Hono } from "hono";
import { jwt } from "hono/jwt";
import { D1Database } from "@cloudflare/workers-types";

type Bindings = { DB: D1Database; JWT_SECRET: string };

const app = new Hono<{ Bindings: Bindings }>();

// JWT middleware
app.use("/api/*", jwt({ secret: (c) => c.env.JWT_SECRET }));

// Login route
app.post("/auth/login", async (c) => {
  const { email, password } = await c.req.json();
  const user = await c.env.DB.prepare("SELECT * FROM users WHERE email = ?")
    .bind(email)
    .first();

  if (!user || !(await verifyPassword(password, user.password_hash))) {
    return c.json({ error: "Invalid credentials" }, 401);
  }

  const token = await sign({ sub: user.id, role: user.role }, c.env.JWT_SECRET);
  return c.json({
    token,
    user: { id: user.id, email: user.email, role: user.role },
  });
});
```

**Option B: Hono + Lucia Auth**

- More feature-complete (sessions, OAuth)
- D1 adapter available
- Slightly more setup

**Option C: Hono + WorkOS/Clerk**

- External auth provider
- Fastest setup
- Monthly cost

### API Structure

```typescript
// api/src/index.ts
import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { authRoutes } from "./routes/auth";
import { tiRoutes } from "./routes/tis";
import { propertyRoutes } from "./routes/properties";
import { documentRoutes } from "./routes/documents";

type Bindings = {
  DB: D1Database;
  R2: R2Bucket;
  JWT_SECRET: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Global middleware
app.use("*", logger());
app.use(
  "*",
  cors({
    origin: ["https://cadeia.example.com", "http://localhost:5173"],
    credentials: true,
  }),
);

// Routes
app.route("/auth", authRoutes);
app.route("/api/tis", tiRoutes);
app.route("/api/properties", propertyRoutes);
app.route("/api/documents", documentRoutes);

// Health check
app.get("/health", (c) => c.json({ status: "ok", timestamp: Date.now() }));

export default app;
```

### Consequences

#### Positive

- ✅ Best-in-class edge performance (<50ms cold start)
- ✅ Tiny bundle size leaves room for business logic
- ✅ Native Cloudflare bindings (D1, R2, KV)
- ✅ Excellent developer experience with TypeScript
- ✅ Clean middleware architecture
- ✅ Easy to test (Hono provides test utilities)

#### Negative

- ❌ No built-in auth (must implement or use library)
- ❌ Smaller ecosystem than Express
- ❌ Team must learn Hono patterns

### Mitigations

| Concern           | Mitigation                                                 |
| ----------------- | ---------------------------------------------------------- |
| No built-in auth  | JWT + D1 is simple; Lucia if OAuth needed                  |
| Smaller ecosystem | Most Node middleware patterns translate; growing community |
| Learning curve    | Hono is simpler than Express; excellent docs               |

### References

- [Hono Documentation](https://hono.dev/)
- [Hono Cloudflare Workers Guide](https://hono.dev/docs/getting-started/cloudflare-workers)
- [Hono Middleware](https://hono.dev/docs/middleware/builtin/jwt)
- [Hono + D1 Example](https://developers.cloudflare.com/d1/examples/d1-and-hono/)
- [Lucia Auth D1 Adapter](https://lucia-auth.com/database/d1)

---

## ADR-003: Database - Cloudflare D1 (SQLite)

**Status**: ✅ **DECIDED** - Cloudflare D1
**Date**: 2025-01-08
**Decision Maker**: Development Team

### Context

Current Django application uses PostgreSQL in production and SQLite in development. Need a database solution compatible with Cloudflare Workers.

### Decision

**Use Cloudflare D1** (SQLite at the edge).

### Rationale

| Factor               | Cloudflare D1                  | PostgreSQL                  | Winner     |
| -------------------- | ------------------------------ | --------------------------- | ---------- |
| **Edge Performance** | Excellent (global replication) | Requires connection pooling | D1         |
| **Cost**             | Free tier generous             | Paid service                | D1         |
| **Operations**       | No servers to manage           | Requires maintenance        | D1         |
| **Features**         | SQLite subset                  | Full PostgreSQL features    | PostgreSQL |
| **Max Size**         | 25GB per database              | Unlimited                   | PostgreSQL |
| **Connections**      | Built-in                       | Connection pooling needed   | D1         |

### Consequences

#### Positive

- ✅ Zero infrastructure management
- ✅ Automatic global replication
- ✅ Free tier up to 5GB
- ✅ Local development with SQLite
- ✅ Fast reads from edge locations

#### Negative

- ❌ SQLite limitations (no partial indexes, limited JSON support)
- ❌ 25GB max size per database
- ❌ No direct PostgreSQL compatibility
- ❌ Migration from PostgreSQL required

### Mitigations

- Use Drizzle ORM for database-agnostic queries
- Implement data archival strategy for size limits
- Use D1 for primary copy, consider R2 for document storage

### References

- [Cloudflare D1 Best Practices](https://developers.cloudflare.com/d1/best-practices/)
- [D1 Getting Started](https://developers.cloudflare.com/d1/get-started/)
- [D1 Local Development](https://developers.cloudflare.com/d1/best-practices/local-development/)

---

## ADR-004: Authentication - Hono JWT + D1

**Status**: ✅ **DECIDED** - Hono JWT with D1
**Date**: 2026-01-08
**Decision Maker**: Development Team
**Supersedes**: Previous decision for NextAuth.js v5 (2025-01-08)

### Context

With the decision to use Hono as the backend framework (ADR-002), authentication needs to be handled within the Hono ecosystem. Requirements:

- Email/password authentication
- Role-based access control (admin, editor, viewer)
- Session/token management
- Future OAuth support if needed

### Decision

**Use Hono's built-in JWT middleware** with D1 for user storage.

### Rationale

| Factor          | Hono JWT + D1     | NextAuth.js           | Lucia Auth          |
| --------------- | ----------------- | --------------------- | ------------------- |
| **Simplicity**  | ✅ Minimal setup  | ⚠️ Framework overhead | ⚠️ More config      |
| **Bundle Size** | ✅ ~2KB           | ❌ ~50KB+             | ⚠️ ~15KB            |
| **D1 Native**   | ✅ Direct queries | ⚠️ Adapter layer      | ✅ D1 adapter       |
| **OAuth**       | ⚠️ Manual         | ✅ Built-in           | ✅ Built-in         |
| **Control**     | ✅ Full           | ⚠️ Framework patterns | ⚠️ Library patterns |
| **Edge Perf**   | ✅ Optimal        | ⚠️ Good               | ✅ Good             |

#### Why JWT + D1 for CadeiaDominial?

1. **Internal Application**: No public registration—OAuth providers not required initially
2. **Simple Roles**: Three roles (admin, editor, viewer)—no complex permission trees
3. **Minimal Overhead**: JWT middleware adds ~2KB vs 50KB+ for NextAuth
4. **Full Control**: Can customize auth flow exactly as needed
5. **Future-Proof**: Can add Lucia Auth later if OAuth becomes required

### Implementation

#### Database Schema (Drizzle)

```typescript
// shared/src/schemas/auth.ts
import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  passwordHash: text("password_hash").notNull(),
  role: text("role", { enum: ["admin", "editor", "viewer"] })
    .notNull()
    .default("viewer"),
  name: text("name"),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
  updatedAt: integer("updated_at", { mode: "timestamp" }).notNull(),
});

export const sessions = sqliteTable("sessions", {
  id: text("id").primaryKey(),
  userId: text("user_id")
    .notNull()
    .references(() => users.id),
  expiresAt: integer("expires_at", { mode: "timestamp" }).notNull(),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
});
```

#### Auth Middleware

```typescript
// api/src/middleware/auth.ts
import { Hono } from "hono";
import { jwt } from "hono/jwt";
import { HTTPException } from "hono/http-exception";

export const authMiddleware = (roles?: string[]) => {
  return async (c, next) => {
    const payload = c.get("jwtPayload");

    if (!payload) {
      throw new HTTPException(401, { message: "Unauthorized" });
    }

    if (roles && !roles.includes(payload.role)) {
      throw new HTTPException(403, { message: "Forbidden" });
    }

    await next();
  };
};

// Usage in routes
app.use("/api/*", jwt({ secret: (c) => c.env.JWT_SECRET }));
app.use("/api/admin/*", authMiddleware(["admin"]));
app.use("/api/edit/*", authMiddleware(["admin", "editor"]));
```

#### Auth Routes

```typescript
// api/src/routes/auth.ts
import { Hono } from "hono";
import { sign, verify } from "hono/jwt";
import { z } from "zod";
import { zValidator } from "@hono/zod-validator";
import bcrypt from "bcryptjs";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export const authRoutes = new Hono()
  .post("/login", zValidator("json", loginSchema), async (c) => {
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
        exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24,
      },
      c.env.JWT_SECRET,
    );

    return c.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      },
    });
  })
  .post("/logout", async (c) => {
    // JWT is stateless; client discards token
    // Optional: add token to blocklist in D1/KV for immediate invalidation
    return c.json({ success: true });
  })
  .get("/me", async (c) => {
    const payload = c.get("jwtPayload");
    const user = await c.env.DB.prepare(
      "SELECT id, email, name, role FROM users WHERE id = ?",
    )
      .bind(payload.sub)
      .first();

    return c.json({ user });
  });
```

### Migration Path to Lucia (If OAuth Needed)

If OAuth providers become required later:

```typescript
// Lucia Auth setup with D1
import { Lucia } from "lucia";
import { D1Adapter } from "@lucia-auth/adapter-sqlite";

export const lucia = new Lucia(
  new D1Adapter(db, {
    user: "users",
    session: "sessions",
  }),
);
```

### Consequences

#### Positive

- ✅ Minimal bundle size (~2KB for JWT middleware)
- ✅ Full control over auth flow
- ✅ Direct D1 queries—no adapter overhead
- ✅ Simple to understand and debug
- ✅ Easy to extend with custom logic

#### Negative

- ❌ Must implement password hashing, token refresh manually
- ❌ No built-in OAuth (must add Lucia later if needed)
- ❌ No built-in session management UI

### Mitigations

| Concern                  | Mitigation                                   |
| ------------------------ | -------------------------------------------- |
| Manual password handling | Use bcryptjs (proven, edge-compatible)       |
| No OAuth                 | Add Lucia Auth when/if OAuth required        |
| Token refresh            | Implement refresh token rotation pattern     |
| Session invalidation     | Use KV/D1 blocklist for immediate revocation |

### References

- [Hono JWT Middleware](https://hono.dev/docs/middleware/builtin/jwt)
- [Hono Authentication Guide](https://hono.dev/docs/guides/authentication)
- [Lucia Auth (future OAuth)](https://lucia-auth.com/)
- [Lucia D1 Adapter](https://lucia-auth.com/database/d1)
- [bcryptjs for Edge](https://www.npmjs.com/package/bcryptjs)

---

## ADR-005: State Management - TanStack Query

**Status**: ✅ **DECIDED** - TanStack Query (React Query)
**Date**: 2025-01-08
**Decision Maker**: Development Team

### Context

Application needs to manage server state, caching, and synchronization for:

- List views (TIs, properties, documents)
- Detail views
- Form submissions
- Tree visualization data

### Decision

**Use TanStack Query** for server state management.

### Rationale

| Factor               | TanStack Query | Redux         | Zustand   | SWR          |
| -------------------- | -------------- | ------------- | --------- | ------------ |
| **Server State**     | ✅ Excellent   | ⚠️ Manual     | ⚠️ Manual | ✅ Good      |
| **Caching**          | ✅ Automatic   | ❌ Manual     | ❌ Manual | ✅ Automatic |
| **Type Safety**      | ✅ Excellent   | ⚠️ Extra work | ✅ Good   | ⚠️ Limited   |
| **tRPC Integration** | ✅ Native      | Possible      | Possible  | Possible     |
| **Bundle Size**      | ~13KB          | Larger        | Small     | Small        |

### Consequences

#### Positive

- ✅ Automatic caching and refetching
- ✅ Optimistic updates
- ✅ Excellent TypeScript support
- ✅ Works seamlessly with tRPC
- ✅ DevTools for debugging

#### Negative

- ❌ Additional library to learn
- ❌ Configuration needed for complex scenarios

### References

- [TanStack Query Documentation](https://tanstack.com/query/latest)

---

## ADR-006: Testing Strategy

**Status**: ✅ **DECIDED** - Vitest + Playwright
**Date**: 2025-01-08
**Decision Maker**: Development Team

### Decision

**Unit Testing**: Vitest (compatible with Vite, faster than Jest)

**E2E Testing**: Playwright (Cloudflare native support)

**Coverage Target**: 80% minimum

### Rationale

| Tool                | Purpose         | Advantage                                   |
| ------------------- | --------------- | ------------------------------------------- |
| **Vitest**          | Unit tests      | Vite-compatible, fast, native ESM           |
| **Playwright**      | E2E tests       | Cloudflare support, reliable, multi-browser |
| **Testing Library** | Component tests | React best practices, user-centric          |
| **MSW**             | API mocking     | Request interception, type-safe             |

### References

- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [Cloudflare + Playwright](https://developers.cloudflare.com/pages/functions/)

---

## ADR-007: Tree Visualization Library - React Flow

**Status**: ✅ **DECIDED** - React Flow
**Date**: 2026-01-26
**Decision Maker**: Development Team

### Context

The frontend needs an interactive graph to visualize `Documento` and `Lancamento` relationships
with pan/zoom, node/edge customization, and support for iterative layouts.

### Decision

Use **React Flow** for the cadeia dominial tree visualization in the React frontend.

### Rationale

- React-native graph API and ecosystem-friendly integration.
- Built-in zoom/pan controls and node/edge customization.
- Good fit for incremental prototyping with minimal D3 interop.

### Consequences

#### Positive

- ✅ React-native primitives for nodes/edges reduce custom D3 glue code.
- ✅ Strong ecosystem with examples and extensions for layout/interaction.
- ✅ Built-in viewport state simplifies fit-to-view and navigation.

#### Negative

- ❌ Large graphs may require layout optimization and render tuning.
- ❌ Complex layouts may need external layout helpers.

### Rejected Options

- **D3.js with React wrapper**: higher integration overhead and more custom glue code for interactions.
- **Vis.js**: heavier dependency with less React-native ergonomics.
- **Custom React implementation**: increased maintenance cost and slower iteration for graph features.

### Implementation Notes

- Data shape: `{ nodes, edges, viewport? }` with `nodes[].id`, `nodes[].position`, `edges[].source`, `edges[].target`.
- Nodes represent `Documento` records; edges represent `Lancamento` links (`documento_origem -> documento`).
- Layout is computed in app code (simple BFS or a layout helper), not in the DB.

### References

- [React Flow Documentation](https://reactflow.dev/)

---

## Pending Decisions

### PD-002: PDF Export Strategy

**Options**:

- jsPDF (client-side, free)
- Puppeteer (server-side, requires Node.js runtime)
- Cloudflare Workers PDF generation
- External service API

**Status**: 🔍 **Under Investigation**

**Constraint**: Cloudflare Workers has limited Node.js APIs

### PD-003: File Storage Strategy

**Options**:

- Cloudflare R2 (S3-compatible, edge-optimized)
- Cloudflare Images (optimized for images only)
- Base64 in database (small files only)

**Status**: 🔍 **Under Investigation**

---

## Decision Template

For future architectural decisions, use this template:

```markdown
## ADR-XXX: [Decision Title]

**Status**: 🔄 **PROPOSED** / ✅ **DECIDED** / ❌ **REJECTED**
**Date**: YYYY-MM-DD
**Decision Maker**: [Name/Role]

### Context

[Background information, problem statement]

### Decision

[Clear statement of the decision]

### Rationale

[Why this decision was made, trade-offs considered]

### Consequences

[Positive and negative impacts]

### Alternatives Considered

[Other options and why they were not chosen]

### References

[Links to relevant documentation, research]
```

---

**Last Updated**: 2026-01-08
**Maintained By**: Development Team
