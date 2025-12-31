# corpsite

Site for hospital's personal cabinets with task and monthly reporting system.

## Features

- **Task Management** - Role-based task assignment with execution tracking
- **Monthly Reports** - Structured reporting with approval workflow
- **Matrix Management** - Support for administrative and functional hierarchies
- **Audit Logging** - Complete tracking of all changes (who/what/when/before/after)
- **PostgreSQL** - BIGINT identifiers and JSONB for flexible data storage

## Database Schema

The database schema is located in `db/schema/`. See:
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - Complete project overview
- [db/schema/README.md](db/schema/README.md) - Detailed schema documentation
- [db/schema/QUICK_REFERENCE.md](db/schema/QUICK_REFERENCE.md) - Common operations guide

## Quick Start

### Install Database Schema

```bash
cd db/schema
./install.sh
```

### Load Sample Data (Optional)

```bash
psql -U postgres -d corpsite -f db/schema/sample_data.sql
```

### Verify Installation

```bash
psql -U postgres -d corpsite -f db/schema/verify.sql
```

## Schema Files

1. `01_users_and_roles.sql` - Users, roles, and user-role associations
2. `02_tasks.sql` - Tasks, task statuses, and task comments
3. `03_reports.sql` - Reports, report types, sections, and task links
4. `04_audit_logging.sql` - Audit log table, triggers, and logging function
5. `05_views_and_functions.sql` - Helper views and utility functions

## Documentation

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - High-level project overview
- [db/schema/README.md](db/schema/README.md) - Comprehensive schema documentation
- [db/schema/QUICK_REFERENCE.md](db/schema/QUICK_REFERENCE.md) - Quick reference for common operations

