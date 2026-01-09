# 📋 Migration Checklist

Checklist for migrating CadeiaDominial from Django to **React + Vite + Hono** on Cloudflare.

---

## Phase 1: Preparation & Planning

### Planning

- [ ] Review current Django application architecture
- [ ] Identify all features to migrate
- [ ] Create feature backlog with priorities
- [ ] Define migration timeline and milestones
- [ ] Identify any external integrations
- [ ] Plan data migration strategy

### Team & Resources

- [ ] Assign team roles (frontend, backend, DevOps)
- [ ] Set up communication channels
- [ ] Schedule knowledge transfer sessions
- [ ] Document Django-specific business logic

### Environment Setup

- [ ] Set up Cloudflare account
- [ ] Create Cloudflare D1 database instances (dev/prod)
- [ ] Configure DNS records (if applicable)
- [ ] Set up GitHub repository
- [ ] Configure CI/CD pipeline

---

## Phase 2: Database Migration

### Schema Analysis

- [ ] Document Django models
- [ ] Map Django models to Drizzle schema
- [ ] Identify relationships (foreign keys, many-to-many)
- [ ] Note any Django-specific features (signals, managers)

### Drizzle Setup

- [ ] Initialize Drizzle configuration
- [ ] Define schema in TypeScript
- [ ] Generate initial migration
- [ ] Test migration locally
- [ ] Set up migration script for existing data

### Data Migration

- [ ] Export data from PostgreSQL
- [ ] Transform data to new schema
- [ ] Import to D1 (staging)
- [ ] Verify data integrity
- [ ] Test application with migrated data

---

## Phase 3: Authentication Migration

### Hono JWT + D1 Setup

- [ ] Install Hono JWT middleware
- [ ] Create users table in Drizzle schema
- [ ] Implement password hashing with bcryptjs
- [ ] Create auth routes (login, logout, /me)
- [ ] Implement role-based access middleware

### User Migration

- [ ] Migrate user accounts from Django
- [ ] Re-hash passwords with bcryptjs (or implement dual-hash migration)
- [ ] Map Django roles to new schema (admin, editor, viewer)
- [ ] Test login flow with migrated users
- [ ] Test role-based access control

### Token Management

- [ ] Configure JWT secret in Cloudflare secrets
- [ ] Implement token expiration (24h default)
- [ ] Create token refresh strategy (if needed)
- [ ] Test token validation across API routes
- [ ] Test logout flow (client-side token discard)

---

## Phase 4: Core Features Migration

### Data Models (Priority: High)

- [ ] Indigenous Lands (TIs)
- [ ] Properties (Imóveis)
- [ ] Documents (Matrículas/Transcrições)
- [ ] Notary Offices (Cartórios)
- [ ] People (Pessoas)
- [ ] Records (Lançamentos)

### CRUD Operations

- [ ] Create operations
- [ ] Read operations (list/detail)
- [ ] Update operations
- [ ] Delete operations
- [ ] Bulk operations

### Business Logic

- [ ] Duplicate detection
- [ ] Validation rules
- [ ] Data relationships
- [ ] Calculated fields
- [ ] Audit trail

---

## Phase 5: UI Components Migration

### Layout & Navigation

- [ ] Main layout component
- [ ] Navigation menu
- [ ] Header/footer
- [ ] Responsive design
- [ ] Dark mode (if needed)

### Forms

- [ ] TI creation form
- [ ] Property creation form
- [ ] Document upload form
- [ ] Search forms
- [ ] Validation and error handling

### Lists & Tables

- [ ] TI list view
- [ ] Property list view
- [ ] Document list view
- [ ] Pagination
- [ ] Sorting and filtering

### Detail Views

- [ ] TI detail page
- [ ] Property detail page
- [ ] Document detail page
- [ ] Related data display
- [ ] Action buttons

---

## Phase 6: Tree Visualization

### D3.js to React Migration

- [ ] Audit existing D3.js code
- [ ] Choose React visualization library
  - [ ] D3.js with React wrapper
  - [ ] React Flow
  - [ ] Vis.js
  - [ ] Custom React implementation
- [ ] Implement tree data structure
- [ ] Render tree component
- [ ] Add zoom controls
- [ ] Add pan controls
- [ ] Implement node selection
- [ ] Show node details on click

### Performance

- [ ] Test with large datasets
- [ ] Implement virtualization (if needed)
- [ ] Add loading states
- [ ] Optimize rendering
- [ ] Add error boundaries

---

## Phase 7: Export Features

### PDF Export

- [ ] Choose PDF library (jsPDF, Puppeteer)
- [ ] Design PDF templates
- [ ] Implement PDF generation
- [ ] Test with various data sizes
- [ ] Add download functionality

### Excel Export

- [ ] Choose Excel library (xlsx, exceljs)
- [ ] Implement Excel generation
- [ ] Format data correctly
- [ ] Test with various data sizes
- [ ] Add download functionality

### JSON Export

- [ ] Implement JSON API endpoint
- [ ] Format data structure
- [ ] Add authentication
- [ ] Test with various data sizes
- [ ] Add download functionality

---

## Phase 8: Testing

### Unit Tests

- [ ] Test data models
- [ ] Test API routes
- [ ] Test utility functions
- [ ] Test business logic
- [ ] Achieve 80%+ coverage

### Integration Tests

- [ ] Test database operations
- [ ] Test authentication flows
- [ ] Test API endpoints
- [ ] Test file uploads
- [ ] Test data export

### E2E Tests

- [ ] Test critical user flows
- [ ] Test authentication
- [ ] Test CRUD operations
- [ ] Test tree visualization
- [ ] Test data export

### Performance Tests

- [ ] Test API response times
- [ ] Test database query performance
- [ ] Test page load times
- [ ] Test tree visualization with large datasets
- [ ] Optimize bottlenecks

---

## Phase 9: Deployment

### Staging Deployment

- [ ] Deploy to staging environment
- [ ] Run smoke tests
- [ ] Test all critical flows
- [ ] Get stakeholder approval
- [ ] Document any issues

### Production Deployment

- [ ] Create production D1 database
- [ ] Run production migrations
- [ ] Migrate production data
- [ ] Deploy to production
- [ ] Configure DNS
- [ ] Enable SSL
- [ ] Test live application
- [ ] Monitor error rates

### Post-Deployment

- [ ] Monitor application performance
- [ ] Check error logs (Sentry)
- [ ] Verify data integrity
- [ ] Test backup and restore
- [ ] Document any issues

---

## Phase 10: Monitoring & Maintenance

### Monitoring Setup

- [ ] Configure Sentry error tracking
- [ ] Set up performance monitoring
- [ ] Configure Cloudflare Analytics
- [ ] Set up uptime monitoring
- [ ] Create alerting rules

### Backup & Recovery

- [ ] Automate D1 backups
- [ ] Test backup restoration
- [ ] Document recovery procedures
- [ ] Schedule regular backup tests

### Documentation

- [ ] Update README
- [ ] Document API endpoints
- [ ] Create deployment guide
- [ ] Create troubleshooting guide
- [ ] Document runbooks

---

## Rollback Plan

### Pre-Migration Backup

- [ ] Backup PostgreSQL database
- [ ] Backup Django media files
- [ ] Backup configuration files
- [ ] Document rollback steps

### Rollback Triggers

- [ ] Define rollback criteria
- [ ] Set monitoring thresholds
- [ ] Create rollback decision tree

### Rollback Procedure

- [ ] Document DNS rollback steps
- [ ] Document database rollback steps
- [ ] Document code rollback steps
- [ ] Test rollback procedure

---

## Post-Migration Tasks

### Cleanup

- [ ] Archive old Django code
- [ ] Remove temporary servers
- [ ] Clean up cloud resources
- [ ] Update documentation

### Optimization

- [ ] Monitor performance metrics
- [ ] Identify slow operations
- [ ] Optimize database queries
- [ ] Implement caching strategies
- [ ] Optimize bundle sizes

### Training

- [ ] Train users on new interface
- [ ] Train developers on new stack
- [ ] Create video tutorials
- [ ] Gather user feedback

---

## Sign-Off

| Phase              | Owner | Status         | Date | Notes |
| ------------------ | ----- | -------------- | ---- | ----- |
| Planning           |       | ⬜ Not Started |      |       |
| Database Migration |       | ⬜ Not Started |      |       |
| Authentication     |       | ⬜ Not Started |      |       |
| Core Features      |       | ⬜ Not Started |      |       |
| UI Components      |       | ⬜ Not Started |      |       |
| Tree Visualization |       | ⬜ Not Started |      |       |
| Export Features    |       | ⬜ Not Started |      |       |
| Testing            |       | ⬜ Not Started |      |       |
| Deployment         |       | ⬜ Not Started |      |       |
| Monitoring         |       | ⬜ Not Started |      |       |
| Post-Migration     |       | ⬜ Not Started |      |       |

---

**Last Updated**: 2026-01-08
**Version**: 2.0.0
