# Schema Relationships and Key Concepts

## Entity Relationship Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         USERS & ROLES                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐         ┌──────────────┐         ┌────────┐        │
│  │  users  │◄───────►│  user_roles  │◄───────►│  roles │        │
│  └─────────┘         └──────────────┘         └────────┘        │
│      │ │                                                         │
│      │ └─ administrative_manager_id (self-reference)            │
│      └─── functional_manager_id (self-reference)                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        TASK MANAGEMENT                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐                                              │
│  │ task_statuses  │  (execution-only: pending, in_progress, etc) │
│  └────────────────┘                                              │
│          ▲                                                       │
│          │                                                       │
│  ┌───────┴──────┐         ┌──────────────────┐                  │
│  │    tasks     │◄────────┤ task_comments    │                  │
│  └──────────────┘         └──────────────────┘                  │
│      │     │                                                     │
│      │     └─── assigned_to_user_id ──► users                   │
│      └───────── assigned_to_role_id ──► roles                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      MONTHLY REPORTS                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                                │
│  │ report_types │                                                │
│  └──────────────┘                                                │
│          ▲                                                       │
│          │                                                       │
│  ┌───────┴──────┐         ┌──────────────────┐                  │
│  │   reports    │◄────────┤ report_sections  │                  │
│  └──────────────┘         └──────────────────┘                  │
│      │   │   │                    │                              │
│      │   │   └── approved_by ────►users                          │
│      │   └────── user_id ────────►users                          │
│      │                                                           │
│      └─────────► report_tasks ────► tasks                        │
│                                                                  │
│  Approval Cycle:                                                │
│    - is_approved (boolean)                                      │
│    - approved_by (user_id)                                      │
│    - approved_at (timestamp)                                    │
│    - Constraint ensures consistency                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                       AUDIT LOGGING                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                                │
│  │  audit_log   │                                                │
│  └──────────────┘                                                │
│      │                                                           │
│      │  Tracks all changes to:                                  │
│      │  - table_name (which table)                              │
│      │  - record_id (which record)                              │
│      │  - operation (INSERT/UPDATE/DELETE)                      │
│      │  - changed_by (who)                                      │
│      │  - changed_at (when)                                     │
│      │  - before_data (JSONB - before state)                    │
│      │  - after_data (JSONB - after state)                      │
│      │  - changed_fields (JSONB - what changed)                 │
│      │                                                           │
│      └──► Automatic triggers on ALL main tables                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Design Patterns

### 1. Matrix Management
```
User
  ├── administrative_manager_id → User (hierarchical)
  └── functional_manager_id → User (hierarchical)
```

### 2. Role-Based Task Assignment
```
Task
  ├── assigned_to_role_id → Role (required)
  └── assigned_to_user_id → User (optional)
```
Tasks are always assigned to a role, optionally to a specific user within that role.

### 3. Execution vs. Approval Separation
```
Tasks:
  └── status_id → task_statuses (execution-only)
      Examples: pending, in_progress, on_hold, completed, cancelled
      
Reports:
  ├── is_approved (boolean)
  ├── approved_by (user_id)
  └── approved_at (timestamp)
  
Approval is a managerial action, NOT an execution status.
```

### 4. Single Approval Cycle
```
Report Approval States:
  
  Draft:
    is_approved = FALSE
    approved_by = NULL
    approved_at = NULL
    submitted_at = NULL
    
  Submitted (Pending):
    is_approved = FALSE
    approved_by = NULL
    approved_at = NULL
    submitted_at = <timestamp>
    
  Approved:
    is_approved = TRUE
    approved_by = <user_id>
    approved_at = <timestamp>
    submitted_at = <timestamp>
    
  Rejected:
    is_approved = FALSE
    approved_by = NULL
    approved_at = NULL
    submitted_at = NULL (reset for resubmission)
    rejection_reason = <text>
```

### 5. Complete Audit Trail
```
Every change triggers:
  
  INSERT:
    ├── after_data = complete new record
    ├── before_data = NULL
    └── changed_fields = NULL
    
  UPDATE:
    ├── after_data = complete new state
    ├── before_data = complete old state
    └── changed_fields = array of field names that changed
    
  DELETE:
    ├── after_data = NULL
    ├── before_data = complete deleted record
    └── changed_fields = NULL
```

## Data Flow Examples

### Task Assignment Flow
```
1. Task created → assigned to Role
2. User with that Role can claim it → assigned_to_user_id set
3. User updates status → in_progress
4. User completes task → status = completed, completed_at set
5. All changes logged in audit_log
```

### Monthly Report Flow
```
1. User creates report → user_id, period_year, period_month
2. User adds sections → report_sections
3. User links tasks → report_tasks
4. User submits → submitted_at set
5. Manager reviews → v_pending_approvals
6. Manager approves → is_approved = TRUE, approved_by, approved_at
7. All changes logged in audit_log
```

### Matrix Management Flow
```
User has:
  ├── Administrative Manager → for HR, admin tasks
  └── Functional Manager → for project, technical tasks
  
Report approval can go to either manager based on context:
  - get_team_reports(manager_id, 'administrative')
  - get_team_reports(manager_id, 'functional')
```

## Database Constraints Summary

### Foreign Keys
- All manager references → users(id)
- Task assignment → roles(id), users(id)
- Report ownership → users(id)
- Report approval → users(id)
- Audit tracking → users(id)

### Unique Constraints
- users: username, email
- roles: name
- user_roles: (user_id, role_id)
- reports: (user_id, period_year, period_month, report_type_id)

### Check Constraints
- tasks.priority: 1-10
- reports.period_month: 1-12
- reports approval consistency: if approved, must have approver and timestamp
- audit_log.operation: INSERT, UPDATE, or DELETE

### Indexes
- All foreign keys
- All timestamp fields (created_at, updated_at, approved_at, etc.)
- Status fields (is_active, is_approved)
- Period fields (period_year, period_month)
- GIN indexes on JSONB columns for efficient querying

## BIGINT Usage

All ID fields use BIGINT (8 bytes) instead of INT (4 bytes):
- INT max: ~2.1 billion
- BIGINT max: ~9.2 quintillion

This ensures scalability for high-volume systems.
