# Task and Monthly Reporting System

## Project Overview

This project implements a comprehensive task and monthly reporting system for a hospital's personal cabinet system. The database schema supports matrix management (both administrative and functional hierarchies), role-based task assignment, and a complete audit trail.

## Key Features

### 1. Matrix Management
- Users can have both an **administrative manager** and a **functional manager**
- Supports complex organizational structures common in healthcare
- Enables reporting to different managers for different purposes

### 2. Role-Based Task Assignment
- Tasks are assigned to **roles** (e.g., Doctor, Nurse, Administrator)
- Optionally assigned to specific users within those roles
- Flexible system that adapts to team changes

### 3. Task Execution Tracking
- Task statuses focus on **execution only** (pending, in_progress, on_hold, completed, cancelled)
- Approval is a separate managerial action handled by the reporting system
- Clear separation of concerns between task execution and management oversight

### 4. Monthly Reporting with Approval Cycle
- Reports stored as **separate entities** from tasks
- **Single approval cycle** with approval tracking (approved_by, approved_at)
- One report per user per period (enforced by database constraints)
- Structured content with sections
- Links to tasks included in the report

### 5. Comprehensive Audit Logging
- **Full audit trail**: who/what/when/before/after
- Automatic triggers on all main tables
- JSONB storage for flexible querying
- Tracks INSERT, UPDATE, and DELETE operations
- Stores complete before/after states for all changes

### 6. PostgreSQL with BIGINT Identifiers
- All ID fields use **BIGINT** data type
- Supports high-volume systems
- Future-proof for large-scale deployments

## Database Schema

### File Structure

```
db/schema/
├── README.md                      # Detailed schema documentation
├── QUICK_REFERENCE.md             # Common operations guide
├── install.sh                     # Installation script
├── 01_users_and_roles.sql        # Users, roles, and associations
├── 02_tasks.sql                   # Tasks and task statuses
├── 03_reports.sql                 # Reports and report sections
├── 04_audit_logging.sql          # Audit log and triggers
├── 05_views_and_functions.sql    # Helper views and functions
├── sample_data.sql                # Sample data for testing
└── verify.sql                     # Verification queries
```

### Core Tables

#### Users and Organization
- `users` - User accounts with matrix management (administrative and functional managers)
- `roles` - Role definitions
- `user_roles` - Many-to-many user-role associations

#### Tasks
- `task_statuses` - Execution status definitions (pending, in_progress, etc.)
- `tasks` - Main task entity with role-based assignment
- `task_comments` - Additional task tracking

#### Reports
- `report_types` - Types of reports (e.g., monthly)
- `reports` - Main report entity with approval cycle
- `report_sections` - Structured report content
- `report_tasks` - Links tasks to reports

#### Audit
- `audit_log` - Complete change history with before/after states

### Views

- `v_users_with_managers` - Users with manager names
- `v_tasks_full` - Tasks with full details
- `v_reports_with_status` - Reports with approval information
- `v_pending_approvals` - Submitted but not yet approved reports

### Functions

- `get_user_tasks(user_id)` - Get tasks for a user based on roles
- `get_team_reports(manager_id, type)` - Get reports for a manager's team
- `get_audit_trail(table, record_id)` - Get complete change history

## Installation

### Prerequisites

- PostgreSQL 12 or higher
- Database and user with appropriate permissions

### Quick Install

```bash
# Set environment variables (optional)
export DB_NAME=corpsite
export DB_USER=postgres
export DB_HOST=localhost
export DB_PORT=5432

# Run installation script
cd db/schema
./install.sh
```

### Manual Install

```bash
cd db/schema
psql -U postgres -d corpsite -f 01_users_and_roles.sql
psql -U postgres -d corpsite -f 02_tasks.sql
psql -U postgres -d corpsite -f 03_reports.sql
psql -U postgres -d corpsite -f 04_audit_logging.sql
psql -U postgres -d corpsite -f 05_views_and_functions.sql
```

### Load Sample Data (Optional)

```bash
psql -U postgres -d corpsite -f sample_data.sql
```

### Verify Installation

```bash
psql -U postgres -d corpsite -f verify.sql
```

## Usage Examples

### Setting Current User for Audit Logging

```sql
SET app.current_user_id = 1;
```

### Creating a Task

```sql
INSERT INTO tasks (
    title, 
    assigned_to_role_id, 
    status_id, 
    priority, 
    created_by, 
    updated_by
)
VALUES (
    'Complete patient assessment',
    (SELECT id FROM roles WHERE name = 'Doctor'),
    (SELECT id FROM task_statuses WHERE name = 'pending'),
    2,
    1,
    1
);
```

### Creating a Monthly Report

```sql
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
    123,
    2025,
    12,
    'December 2025 Report',
    'Monthly activities summary',
    123,
    123
);
```

### Approving a Report

```sql
SET app.current_user_id = 456; -- Manager's ID

UPDATE reports
SET is_approved = TRUE,
    approved_by = 456,
    approved_at = CURRENT_TIMESTAMP,
    updated_by = 456
WHERE id = 789;
```

### Viewing Pending Approvals

```sql
SELECT * FROM v_pending_approvals;
```

### Getting User's Tasks

```sql
SELECT * FROM get_user_tasks(123);
```

### Viewing Audit Trail

```sql
SELECT * FROM get_audit_trail('reports', 789);
```

## Design Principles

1. **Separation of Concerns**
   - Task statuses describe execution state
   - Approval is a managerial action on reports
   - Clear boundaries between operational and management layers

2. **Matrix Management Support**
   - Dual reporting structure (administrative and functional)
   - Flexible organizational modeling
   - Supports complex hierarchies

3. **Role-Based Access**
   - Tasks assigned to roles for flexibility
   - Users can have multiple roles
   - System adapts to team changes

4. **Single Approval Cycle**
   - Reports have one approval workflow
   - Clear approval tracking (who, when)
   - Constraints ensure data integrity

5. **Complete Audit Trail**
   - Every change is logged
   - Before/after states preserved
   - Who/what/when fully tracked

6. **Scalability**
   - BIGINT identifiers for large-scale use
   - Indexed for performance
   - JSONB for flexible audit querying

## Documentation

- **README.md** - Complete schema documentation
- **QUICK_REFERENCE.md** - Common operations and queries
- This document - Project overview

## Development

### Adding New Features

1. Create new SQL file with appropriate naming (e.g., `06_new_feature.sql`)
2. Update `install.sh` to include new file
3. Add relevant views/functions to `05_views_and_functions.sql`
4. Update documentation

### Testing

Run verification queries to ensure schema integrity:
```bash
psql -U postgres -d corpsite -f verify.sql
```

## License

See main repository for license information.

## Support

For issues or questions, please refer to the main repository documentation.
