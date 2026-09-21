# OPS-031 — local neutral EMPLOYEE account provisioning

The script creates only explicitly named local accounts and always assigns the
neutral `EMPLOYEE` Platform Role. It never accepts a role or password from the
command line, environment, or file.

## Preconditions

- Apply the primary personnel migration `emp001employee`.
- Each target Employee is active, operationally `active`, and has Person and
  org-unit links.
- No User is already linked to the Employee, and no normalized login conflict
  exists.
- The resulting User would receive no active allow-grants through role,
  employee, person, assignment, position, or org unit.

## Dry run

This checks every precondition without prompting for a password and without
writing data:

```powershell
venv\Scripts\python.exe scripts\provision_employee_accounts.py `
  --dry-run `
  --account 13:akiltaeva.bs `
  --account 15:musabekov.ka
```

## Apply

Run the same command without `--dry-run`. The script asks once through
`getpass`; that one value is used only to hash both new local accounts. All
preflight checks, both inserts, and the generic plus security audit entries are
one transaction. Any conflict or audit failure rolls back the entire run.

```powershell
venv\Scripts\python.exe scripts\provision_employee_accounts.py `
  --account 13:akiltaeva.bs `
  --account 15:musabekov.ka
```
