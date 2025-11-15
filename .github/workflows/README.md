# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing and deployment of the Sistema de Cadeia Dominial.

## Workflows

### 1. PR Checks and Preview Deployments (`pr-checks.yml`)

**Trigger:** Pull requests to `main` or `develop` branches

**What it does:**
- Detects which parts of the codebase changed (backend vs frontend)
- Runs appropriate test suites based on changes
- Creates preview deployments for changed components

**Jobs:**
- `detect-changes`: Determines if backend and/or frontend changed
- `backend-tests`: Runs pytest unit tests (if backend changed)
- `frontend-tests`: Runs Playwright E2E tests (if frontend changed)
- `deploy-backend-preview`: Deploys backend to Cloudflare Workers preview (if backend changed)
- `deploy-frontend-preview`: Deploys frontend to Cloudflare Pages preview (if frontend changed)

### 2. Production Deployment (`deploy-production.yml`)

**Trigger:** Push to `main` branch

**What it does:**
- Detects which parts of the codebase changed
- Runs full test suites before deployment
- Deploys to production only if tests pass
- Skips unnecessary deployments if code didn't change

**Jobs:**
- `detect-changes`: Determines if backend and/or frontend changed
- `backend-tests`: Runs pytest unit tests (if backend changed)
- `frontend-tests`: Runs Playwright E2E tests (if frontend changed)
- `deploy-backend-production`: Deploys backend to Cloudflare Workers production (if backend changed)
- `deploy-frontend-production`: Deploys frontend to Cloudflare Pages production (if frontend changed)
- `notify-deployment-complete`: Sends deployment summary notification

## Configuration

### Required GitHub Secrets

Add these secrets in your repository settings (`Settings > Secrets and variables > Actions`):

#### Cloudflare Credentials
- `CLOUDFLARE_API_TOKEN`: Your Cloudflare API token with Workers and Pages permissions
- `CLOUDFLARE_ACCOUNT_ID`: Your Cloudflare account ID

#### Production Environment Variables
- `PRODUCTION_DATABASE_URL`: PostgreSQL connection string for production database
- `PRODUCTION_SECRET_KEY`: Django secret key for production
- `PRODUCTION_ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### Path Configuration

Both workflows use the same path filters to detect changes. Update these in both files if your directory structure changes:

```yaml
filters: |
  backend:
    - 'dominial/**'           # Django app directory
    - 'cadeia_dominial/**'     # Django project directory
    - 'requirements.txt'       # Python dependencies
    - 'requirements-test.txt'  # Test dependencies
    - 'pytest.ini'             # Pytest configuration
    - 'manage.py'              # Django management script
  frontend:
    - 'static/**'              # Static files (CSS, JS)
    - 'templates/**'           # Django templates
    - 'playwright.config.py'   # Playwright configuration
```

### Cloudflare Configuration

#### Frontend (Cloudflare Pages)

Update these placeholders in both workflow files:
- `projectName: your-frontend-project-name` → Your Cloudflare Pages project name
- `https://your-frontend-project-name.pages.dev` → Your actual Pages domain

#### Backend (Cloudflare Workers)

Update these placeholders in both workflow files:
- `workingDirectory: ./backend` → Path to your Workers code (if different)
- `https://backend-pr-X.your-workers-domain.workers.dev` → Your Workers preview domain
- `https://api.your-production-domain.com` → Your production API domain

**Note:** You'll also need a `wrangler.toml` file in your backend directory for Cloudflare Workers deployment.

### Python Version

Current configuration uses Python 3.11. To change:

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'  # Change this version
```

### PostgreSQL Version

Current configuration uses PostgreSQL 15. To change:

```yaml
services:
  postgres:
    image: postgres:15  # Change this version
```

## Test Configuration

### Backend Tests

Backend tests run with these pytest markers:
```bash
pytest -m "not e2e"  # Runs all tests except E2E
```

To change what tests run, update the command in the workflow:
```yaml
- name: Run backend tests
  run: |
    pytest -m "not e2e" --cov=dominial --cov-report=xml
```

### Frontend/E2E Tests

E2E tests run with Playwright:
```bash
pytest -m e2e --video=retain-on-failure --screenshot=only-on-failure
```

To change Playwright behavior, update:
```yaml
- name: Run Playwright tests
  run: |
    pytest -m e2e --video=retain-on-failure --screenshot=only-on-failure
```

## Environment Protection Rules

The workflows use GitHub Environments for production deployments. To configure:

1. Go to `Settings > Environments`
2. Create environments:
   - `production-backend`
   - `production-frontend`
3. Add protection rules:
   - Required reviewers
   - Wait timer
   - Deployment branches (limit to `main`)

## Customization Examples

### Add Slack Notifications

Add to the end of `deploy-production.yml`:

```yaml
- name: Notify Slack
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Production deployment complete: ${{ needs.deploy-backend-production.result }} / ${{ needs.deploy-frontend-production.result }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Add Database Migrations

Add before the deploy step in `deploy-backend-production`:

```yaml
- name: Run database migrations
  run: |
    python manage.py migrate --noinput
  env:
    DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
```

### Add Custom Test Reports

Add after test steps:

```yaml
- name: Publish test results
  uses: EnricoMi/publish-unit-test-result-action@v2
  if: always()
  with:
    files: |
      test-results/**/*.xml
```

## Troubleshooting

### Tests not running
- Check the `detect-changes` job output to see if changes were detected
- Verify the path filters match your directory structure

### Deployment failing
- Check that all required secrets are set
- Verify Cloudflare API token has correct permissions
- Check Cloudflare account ID is correct

### Database connection issues in tests
- Ensure PostgreSQL service is starting correctly
- Check environment variables are set correctly
- Verify database credentials in the workflow

### Playwright tests failing
- Ensure `playwright install` runs successfully
- Check that migrations run before tests
- Verify live server is accessible during tests

## Coverage Reports

Backend test coverage is uploaded to Codecov. To enable:

1. Sign up at [codecov.io](https://codecov.io)
2. Add your repository
3. No additional secrets needed (uses `GITHUB_TOKEN`)

Coverage reports are available at: `https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO`

## Cost Optimization

These workflows are designed to minimize CI/CD costs:

- **Smart detection**: Only runs tests/deploys for changed code
- **Parallel jobs**: Backend and frontend tests run simultaneously
- **Conditional execution**: Skips unnecessary steps
- **Caching**: Uses pip caching to speed up builds
- **Database reuse**: PostgreSQL service only starts when needed

Estimated GitHub Actions minutes per PR:
- Backend only: ~5-8 minutes
- Frontend only: ~8-12 minutes (Playwright slower)
- Both changed: ~10-15 minutes (parallel execution)

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cloudflare Pages Documentation](https://developers.cloudflare.com/pages)
- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers)
- [pytest Documentation](https://docs.pytest.org/)
- [Playwright Documentation](https://playwright.dev/)
