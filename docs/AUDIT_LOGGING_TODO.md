# Audit Logging Implementation TODO

## Overview

Based on PR review feedback, the application currently lacks comprehensive audit trails for critical actions. This document outlines the requirements and implementation plan for adding audit logging.

## Requirements

### Critical Actions Requiring Audit Logs

1. **User Authentication**
   - Login attempts (successful and failed)
   - Logout events
   - Password changes
   - Session creation/termination

2. **Data Modification**
   - Lancamento (transaction) creation, updates, deletion
   - Documento (document) creation, updates, deletion
   - Imovel (property) creation, updates, deletion, archiving
   - TI (indigenous territory) creation, updates, deletion

3. **Relationship Changes**
   - Pessoa (person) associations with transactions
   - Origin document linking
   - Document transfers between cartórios

4. **System Configuration**
   - User permission changes
   - System settings modifications
   - Import operations

## Recommended Implementation

### Option 1: Django Simple History (Recommended)

```bash
pip install django-simple-history
```

**Advantages:**
- Automatic tracking of all model changes
- Built-in admin interface
- Historical snapshots
- Minimal code changes

**Implementation:**
```python
from simple_history.models import HistoricalRecords

class Lancamento(models.Model):
    # existing fields...
    history = HistoricalRecords()
```

### Option 2: Custom Audit Log Model

```python
class AuditLog(models.Model):
    """Comprehensive audit trail for system actions."""

    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('import', 'Imported'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField(null=True)
    object_repr = models.CharField(max_length=200)
    changes = models.JSONField(null=True)  # Store field changes
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]
```

### Option 3: Django Auditlog

```bash
pip install django-auditlog
```

**Features:**
- Automatic logging of model changes
- Actor tracking (who made the change)
- Change diffs
- Admin integration

## Implementation Steps

### Phase 1: Basic Audit Logging (Week 1)
1. Choose implementation approach (recommend django-simple-history)
2. Add to requirements.txt
3. Configure in settings.py
4. Add to critical models (Lancamento, Documento, Imovel)
5. Run migrations

### Phase 2: Enhanced Logging (Week 2)
6. Add authentication event logging
7. Add IP address and user agent tracking
8. Create admin interface for viewing logs
9. Add filtering and search capabilities

### Phase 3: Reporting & Compliance (Week 3)
10. Create audit report views
11. Add export functionality (PDF, Excel)
12. Implement log retention policy
13. Add compliance checks

## Code Review Compliance

**From PR Review:**
> "The added tests and configurations introduce user login and record-creation workflows but do not add or verify any audit logging for critical actions, which may indicate missing audit trails in the implemented paths."

**Solution:**
- Add audit logging to all critical workflows
- Include audit log verification in E2E tests
- Verify audit logs are created for:
  - User login (test_login_workflow)
  - Lancamento creation (test_create_registro_lancamento_complete_workflow)
  - Document creation workflows
  - All CRUD operations

## Testing Requirements

### Unit Tests
```python
def test_lancamento_creation_creates_audit_log(self, db):
    """Test that creating a lancamento creates an audit log."""
    # Create lancamento
    lancamento = LancamentoFactory()

    # Verify audit log created
    audit_log = AuditLog.objects.filter(
        model_name='Lancamento',
        object_id=lancamento.id,
        action='create'
    )
    assert audit_log.exists()
```

### E2E Tests
```python
def test_login_creates_audit_trail(self, authenticated_page, db):
    """Test that login creates audit trail."""
    # Verify audit log for login
    audit_log = AuditLog.objects.filter(
        action='login',
        user__username='testuser'
    ).order_by('-timestamp').first()

    assert audit_log is not None
    assert audit_log.ip_address is not None
```

## Security Considerations

1. **Immutable Logs**: Audit logs should not be modifiable or deletable (except by superuser)
2. **PII Protection**: Be careful not to log sensitive PII unnecessarily
3. **Log Retention**: Define retention policy (recommend 7 years for legal compliance)
4. **Access Control**: Only authorized users should view audit logs
5. **Tampering Detection**: Consider cryptographic signatures for log entries

## Performance Considerations

1. **Database Indexes**: Add indexes on timestamp, user, and model_name fields
2. **Log Rotation**: Implement automatic archiving of old logs
3. **Async Logging**: Consider using Celery for async log writing to avoid blocking requests
4. **Partitioning**: For high-volume systems, consider table partitioning by date

## Monitoring & Alerting

1. **Failed Login Attempts**: Alert on multiple failed logins from same IP
2. **Bulk Deletions**: Alert on deletion of multiple records
3. **Suspicious Activity**: Monitor for unusual patterns
4. **Log Storage**: Monitor disk usage for audit log storage

## References

- Django Simple History: https://django-simple-history.readthedocs.io/
- Django Auditlog: https://django-auditlog.readthedocs.io/
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- LGPD (Brazilian Data Protection Law) compliance requirements

## Timeline

- **Week 1**: Implementation decision and basic setup
- **Week 2**: Full implementation and testing
- **Week 3**: Documentation and compliance verification
- **Week 4**: Production deployment and monitoring setup

## Status

- [ ] Decision on implementation approach
- [ ] Requirements review with stakeholders
- [ ] Implementation
- [ ] Testing
- [ ] Documentation
- [ ] Production deployment
- [ ] Compliance verification
