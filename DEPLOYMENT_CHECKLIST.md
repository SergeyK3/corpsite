# Deployment Checklist

This checklist ensures a smooth deployment of the task and monthly reporting system database schema.

## Pre-Deployment

### Environment Preparation
- [ ] PostgreSQL 12 or higher installed and running
- [ ] Database user created with appropriate permissions
- [ ] Database created (e.g., `corpsite`)
- [ ] Backup of existing database (if applicable)
- [ ] Network connectivity to database server verified
- [ ] Application code updated to work with new schema
- [ ] Environment variables configured (if using install.sh)

### Review and Testing
- [ ] All schema files reviewed and approved
- [ ] Code review completed and feedback addressed
- [ ] Schema tested on development environment
- [ ] Sample data loaded and verified on development
- [ ] Application tested against development database
- [ ] Performance testing completed (if applicable)
- [ ] Security review completed

### Documentation Review
- [ ] README.md reviewed and understood
- [ ] QUICK_REFERENCE.md available for developers
- [ ] SCHEMA_DESIGN.md reviewed for understanding
- [ ] MIGRATION_GUIDE.md available for future changes
- [ ] PROJECT_OVERVIEW.md shared with stakeholders

## Deployment Steps

### 1. Backup (if existing database)
```bash
# Create backup
pg_dump -U postgres -h localhost -d corpsite -F c -f corpsite_backup_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list corpsite_backup_*.dump | head -20
```

### 2. Schema Installation

#### Option A: Using install.sh
```bash
# Set environment variables
export DB_NAME=corpsite
export DB_USER=postgres
export DB_HOST=localhost
export DB_PORT=5432

# Run installation
cd db/schema
./install.sh
```

#### Option B: Manual Installation
```bash
cd db/schema
psql -h localhost -U postgres -d corpsite -f 01_users_and_roles.sql
psql -h localhost -U postgres -d corpsite -f 02_tasks.sql
psql -h localhost -U postgres -d corpsite -f 03_reports.sql
psql -h localhost -U postgres -d corpsite -f 04_audit_logging.sql
psql -h localhost -U postgres -d corpsite -f 05_views_and_functions.sql
```

### 3. Verification
```bash
# Run verification queries
psql -h localhost -U postgres -d corpsite -f verify.sql > verification_results.txt

# Review results
cat verification_results.txt
```

### 4. Load Initial Data (Optional)
```bash
# Load sample data for testing
psql -h localhost -U postgres -d corpsite -f sample_data.sql

# OR create your own initial data
psql -h localhost -U postgres -d corpsite -f production_initial_data.sql
```

### 5. Create Bootstrap User
```sql
-- Connect to database
psql -h localhost -U postgres -d corpsite

-- Create first admin user
INSERT INTO users (username, email, full_name, created_by, updated_by)
VALUES ('admin', 'admin@yourdomain.com', 'System Administrator', NULL, NULL);

-- Create initial roles
INSERT INTO roles (name, description, created_by, updated_by)
VALUES 
    ('Administrator', 'System administrator', 1, 1),
    ('Manager', 'Department manager', 1, 1),
    ('User', 'Regular user', 1, 1);

-- Assign admin role
INSERT INTO user_roles (user_id, role_id, assigned_by)
VALUES (1, 1, 1);
```

### 6. Application Configuration
- [ ] Update application database connection strings
- [ ] Configure application to set `app.current_user_id` session variable
- [ ] Update application code to use new schema
- [ ] Configure application authentication/authorization
- [ ] Test application connection to database

### 7. Smoke Tests
```sql
-- Test user creation
SET app.current_user_id = 1;
INSERT INTO users (username, email, full_name, created_by, updated_by)
VALUES ('testuser', 'test@example.com', 'Test User', 1, 1);

-- Test task creation
INSERT INTO tasks (
    title, 
    assigned_to_role_id, 
    status_id, 
    created_by, 
    updated_by
)
VALUES (
    'Test Task',
    (SELECT id FROM roles WHERE name = 'User'),
    (SELECT id FROM task_statuses WHERE name = 'pending'),
    1,
    1
);

-- Test report creation
INSERT INTO reports (
    report_type_id,
    user_id,
    period_year,
    period_month,
    title,
    content,
    created_by,
    updated_by
)
VALUES (
    (SELECT id FROM report_types WHERE name = 'monthly'),
    2,
    2025,
    12,
    'Test Report',
    'Test content',
    1,
    1
);

-- Verify audit log
SELECT COUNT(*) FROM audit_log;

-- Cleanup test data
DELETE FROM reports WHERE title = 'Test Report';
DELETE FROM tasks WHERE title = 'Test Task';
DELETE FROM users WHERE username = 'testuser';
```

## Post-Deployment

### Verification
- [ ] All tables created successfully
- [ ] All indexes created successfully
- [ ] All triggers created successfully
- [ ] All views created successfully
- [ ] All functions created successfully
- [ ] Audit logging working correctly
- [ ] Application can connect to database
- [ ] Application can perform basic operations
- [ ] Sample operations tested (create user, task, report)

### Monitoring
- [ ] Database connection monitoring enabled
- [ ] Query performance monitoring enabled
- [ ] Audit log size monitoring enabled
- [ ] Backup schedule configured
- [ ] Alert thresholds configured

### Documentation
- [ ] Deployment notes documented
- [ ] Known issues documented (if any)
- [ ] Rollback procedure documented
- [ ] Support contact information shared
- [ ] User training materials prepared

### Security
- [ ] Database user permissions verified
- [ ] Application user permissions verified
- [ ] Audit logging enabled and tested
- [ ] Sensitive data handling reviewed
- [ ] Backup encryption configured (if applicable)

## Rollback Procedure

If deployment fails:

1. **Stop Application**
   ```bash
   # Stop application server
   systemctl stop your-application
   ```

2. **Restore Database**
   ```bash
   # Drop current database
   dropdb -h localhost -U postgres corpsite
   
   # Recreate database
   createdb -h localhost -U postgres corpsite
   
   # Restore from backup
   pg_restore -h localhost -U postgres -d corpsite corpsite_backup_*.dump
   ```

3. **Verify Restoration**
   ```bash
   psql -h localhost -U postgres -d corpsite -c "\dt"
   ```

4. **Restart Application**
   ```bash
   systemctl start your-application
   ```

5. **Document Failure**
   - Document what went wrong
   - Create issue for investigation
   - Schedule retry with fixes

## Success Criteria

Deployment is successful when:
- [ ] All schema files installed without errors
- [ ] All verification queries pass
- [ ] Application can connect to database
- [ ] Users can be created and authenticated
- [ ] Tasks can be created and assigned
- [ ] Reports can be created and approved
- [ ] Audit log captures all changes
- [ ] No errors in application logs
- [ ] No errors in database logs
- [ ] Performance is acceptable

## Post-Deployment Tasks

### Week 1
- [ ] Monitor database performance
- [ ] Monitor audit log growth
- [ ] Collect user feedback
- [ ] Address any immediate issues
- [ ] Optimize queries if needed

### Month 1
- [ ] Review audit logs for patterns
- [ ] Analyze query performance
- [ ] Review and optimize indexes
- [ ] Plan for data archival (if needed)
- [ ] Update documentation based on usage

### Ongoing
- [ ] Regular backups verified
- [ ] Database maintenance scheduled (VACUUM, ANALYZE)
- [ ] Monitor table growth
- [ ] Review and archive old audit logs
- [ ] Keep documentation updated

## Support Information

### Database Administrator
- Name: _______________
- Contact: _______________
- Availability: _______________

### Application Team
- Team: _______________
- Contact: _______________
- Escalation: _______________

### Documentation
- Main README: `README.md`
- Schema Documentation: `db/schema/README.md`
- Quick Reference: `db/schema/QUICK_REFERENCE.md`
- Migration Guide: `db/schema/MIGRATION_GUIDE.md`

## Notes

Additional deployment notes:

_______________________________________________________________

_______________________________________________________________

_______________________________________________________________

Deployment Date: _______________
Deployed By: _______________
Deployment Status: _______________
