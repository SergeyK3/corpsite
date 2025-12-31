# Database Schema Documentation

## Overview

This database schema implements a task and monthly reporting system with matrix management support (administrative and functional hierarchies). The system uses PostgreSQL with BIGINT identifiers and comprehensive audit logging.

## Key Features

- **Matrix Management**: Users can have both administrative and functional managers
- **Role-Based Task Assignment**: Tasks are assigned to roles, optionally to specific users
- **Execution-Only Task Statuses**: Task statuses track execution progress, not approval
- **Monthly Reports**: Separate entity with single approval cycle
- **Full Audit Logging**: Complete tracking of who changed what, when, and the before/after states

## Schema Files

The schema is organized into the following files (execute in order):

1. **01_users_and_roles.sql** - Users, roles, and user-role associations
2. **02_tasks.sql** - Tasks, task statuses, and task comments
3. **03_reports.sql** - Reports, report types, sections, and task links
4. **04_audit_logging.sql** - Audit log table, triggers, and logging function
5. **05_views_and_functions.sql** - Helper views and utility functions

## Core Tables

### Users and Roles

#### `users`
- Stores user information with matrix management support
- Fields: id, username, email, full_name, administrative_manager_id, functional_manager_id
- Each user can have both an administrative and functional manager
- Tracks who created/updated each record

#### `roles`
- Defines roles for task assignment
- Fields: id, name, description, is_active

#### `user_roles`
- Many-to-many relationship between users and roles
- A user can have multiple roles
- Tasks are assigned to roles, not individual users (unless specifically assigned)

### Tasks

#### `task_statuses`
- Defines execution statuses (not approval states)
- Default statuses: pending, in_progress, on_hold, completed, cancelled
- Display order for UI presentation

#### `tasks`
- Main task entity
- Assigned to a role (required) and optionally to a specific user
- Status tracks execution progress only
- Priority: 1 (highest) to 10 (lowest)
- Fields: id, title, description, assigned_to_role_id, assigned_to_user_id, status_id, due_date, priority

#### `task_comments`
- Additional tracking and communication on tasks
- Links to task and tracks who created the comment

### Reports

#### `report_types`
- Types of reports (e.g., monthly)
- Extensible for future report types

#### `reports`
- Main report entity with single approval cycle
- One report per user per period (enforced by unique constraint)
- Approval fields: is_approved, approved_by, approved_at
- Constraint ensures approval consistency (if approved, must have approver and timestamp)
- Fields: id, user_id, period_year, period_month, title, content, is_approved, approved_by, approved_at

#### `report_sections`
- Structured content for reports
- Allows reports to have multiple sections
- Display order for consistent presentation

#### `report_tasks`
- Links tasks to reports
- Shows which tasks were included in a report
- Optional notes for additional context

### Audit Logging

#### `audit_log`
- Comprehensive audit trail for all changes
- Tracks: table_name, record_id, operation (INSERT/UPDATE/DELETE)
- Before/after states stored as JSONB
- Changed fields tracked for updates
- Who (changed_by), what (before_data/after_data), when (changed_at)
- Optional IP address and user agent tracking

## Triggers

All main tables have audit triggers that automatically log changes:
- users
- roles
- user_roles
- task_statuses
- tasks
- task_comments
- report_types
- reports
- report_sections
- report_tasks

## Views

### `v_users_with_managers`
Users with their manager names (both administrative and functional)

### `v_tasks_full`
Tasks with full details including role name, user name, status name, and creator name

### `v_reports_with_status`
Reports with reporter name, approver name, and all status information

### `v_pending_approvals`
Reports that have been submitted but not yet approved, with days pending

## Functions

### `get_user_tasks(user_id)`
Returns tasks assigned to a user based on their roles

### `get_team_reports(manager_id, management_type)`
Returns reports for a manager's team (administrative or functional)

### `get_audit_trail(table_name, record_id)`
Returns the complete audit trail for a specific record

## Data Types

- **All IDs**: BIGINT (using BIGSERIAL for auto-increment)
- **Timestamps**: TIMESTAMP WITH TIME ZONE
- **Audit Data**: JSONB for flexible storage and querying

## Indexes

All tables have appropriate indexes for:
- Foreign keys
- Query performance (status, dates, etc.)
- GIN indexes on JSONB columns for efficient querying

## Application Integration

### Setting Current User for Audit Logging

Before performing operations, the application should set the current user ID:

```sql
SET app.current_user_id = <user_id>;
```

This allows the audit triggers to track who made each change.

### Example Queries

#### Get pending tasks for a user
```sql
SELECT * FROM get_user_tasks(123);
```

#### Get team's pending reports (administrative)
```sql
SELECT * FROM get_team_reports(456, 'administrative');
```

#### Get audit trail for a specific report
```sql
SELECT * FROM get_audit_trail('reports', 789);
```

#### Approve a report
```sql
UPDATE reports 
SET is_approved = TRUE, 
    approved_by = <manager_id>, 
    approved_at = CURRENT_TIMESTAMP,
    updated_by = <manager_id>
WHERE id = <report_id>;
```

## Design Principles

1. **Separation of Concerns**: Task statuses describe execution; approval is a separate managerial action
2. **Matrix Management**: Support both administrative and functional hierarchies
3. **Role-Based Assignment**: Tasks assigned to roles for flexibility
4. **Single Approval Cycle**: Reports have one approval workflow (approved_by, approved_at)
5. **Full Audit Trail**: Every change is logged with who/what/when/before/after
6. **Data Integrity**: Constraints ensure consistency (e.g., approved reports must have approver)

## Installation

To install the schema, execute the SQL files in order:

```bash
psql -U <username> -d <database> -f db/schema/01_users_and_roles.sql
psql -U <username> -d <database> -f db/schema/02_tasks.sql
psql -U <username> -d <database> -f db/schema/03_reports.sql
psql -U <username> -d <database> -f db/schema/04_audit_logging.sql
psql -U <username> -d <database> -f db/schema/05_views_and_functions.sql
```

Or use a single command:

```bash
cat db/schema/*.sql | psql -U <username> -d <database>
```
