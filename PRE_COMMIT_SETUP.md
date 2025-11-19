# Pre-commit Hooks Setup Guide

This project uses pre-commit hooks to ensure code quality and consistency before commits.

## Installation

1. **Install pre-commit and quality tools:**
   ```bash
   pip install -r requirements-test.txt
   ```

2. **Install the git hook scripts:**
   ```bash
   pre-commit install
   ```

3. **Verify installation:**
   ```bash
   pre-commit --version
   ```

## Usage

### Automatic (Recommended)

Once installed, pre-commit hooks run automatically on `git commit`:

```bash
git add .
git commit -m "Your commit message"
# Hooks will run automatically
```

If any hook fails:
- The commit will be blocked
- Files will be auto-fixed where possible (Black, isort)
- Review the changes and re-commit

### Manual Execution

Run hooks on all files:
```bash
pre-commit run --all-files
```

Run hooks on specific files:
```bash
pre-commit run --files dominial/models/*.py
```

Run specific hook:
```bash
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run pytest-quick --all-files
```

### Skip Hooks (Use Sparingly)

Skip all hooks for a commit:
```bash
git commit -m "Emergency fix" --no-verify
```

## Hooks Configuration

### Code Formatting
- **Black** - Automatic Python code formatting (line length: 119)
- **isort** - Import statement sorting (Black-compatible profile)

### Linting
- **flake8** - Python linting (max line length: 119, ignores E203, W503)
  - Includes docstring checks via flake8-docstrings

### Django-Specific
- **django-upgrade** - Ensures Django 5.2+ best practices

### Security
- **bandit** - Security vulnerability scanner
  - Configured in pyproject.toml
  - Skips test files (B101: assert_used)

### File Quality
- **trailing-whitespace** - Removes trailing whitespace
- **end-of-file-fixer** - Ensures newline at end of file
- **check-yaml** - Validates YAML syntax
- **check-json** - Validates JSON syntax
- **check-added-large-files** - Prevents large files (>500KB)
- **check-merge-conflict** - Detects merge conflict markers
- **debug-statements** - Catches forgotten debug statements
- **mixed-line-ending** - Ensures consistent line endings

### Testing
- **pytest-quick** - Runs fast tests (excludes e2e and slow tests)
  - Only runs on commit
  - Max 3 failures before stopping
  - Helps catch breaking changes early

## Configuration Files

- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `pyproject.toml` - Tool-specific settings (Black, isort, Bandit, pytest)
- `pytest.ini` - Legacy pytest configuration (being migrated to pyproject.toml)

## Troubleshooting

### Hook installation fails
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Hooks are slow
```bash
# Skip slow tests in pre-commit
# (pytest-quick already excludes e2e and slow tests)

# Or skip pytest entirely for a commit
SKIP=pytest-quick git commit -m "Message"
```

### Update hooks to latest versions
```bash
pre-commit autoupdate
```

### Cache issues
```bash
# Clean pre-commit cache
pre-commit clean
```

## Best Practices

1. **Run hooks before pushing:**
   ```bash
   pre-commit run --all-files
   ```

2. **Fix formatting before committing:**
   ```bash
   black dominial/
   isort dominial/
   ```

3. **Check security issues:**
   ```bash
   bandit -r dominial/ -c pyproject.toml
   ```

4. **Run full test suite before PR:**
   ```bash
   pytest dominial/tests/
   ```

5. **Keep hooks updated:**
   ```bash
   pre-commit autoupdate  # Monthly
   ```

## Integration with CI/CD

Pre-commit hooks match CI/CD pipeline checks:
- Same Black/isort/flake8 configuration
- Same pytest markers and settings
- Early feedback before pushing

## Disabling Specific Hooks

Edit `.pre-commit-config.yaml` and comment out unwanted hooks:

```yaml
#  - repo: https://github.com/PyCQA/bandit
#    rev: 1.7.10
#    hooks:
#      - id: bandit
```

Then update:
```bash
pre-commit install
```

## Getting Help

- **Pre-commit docs:** https://pre-commit.com/
- **Black docs:** https://black.readthedocs.io/
- **isort docs:** https://pycqa.github.io/isort/
- **flake8 docs:** https://flake8.pycqa.org/
- **Bandit docs:** https://bandit.readthedocs.io/
