# Corpsite Pilot Week 1 Checklist

This checklist is for the first controlled rollout in one department.
Goal: launch one working task flow, collect feedback, and avoid chaotic support.

## Pilot scope

Use the first pilot only for:

- one department
- one coordinator / manager
- two or three executors
- one real weekly task flow

Do not expand the pilot until this flow is stable.

## Before day 1

1. Confirm production config:
   - `APP_ENV=prod`
   - `NEXT_PUBLIC_APP_ENV=prod`
   - `ENABLE_DIRECTORY_DEBUG=0`
   - `ENABLE_LEGACY_X_USER_ID=0`
   - `AUTH_JWT_SECRET` is non-default
   - `INTERNAL_API_TOKEN` matches backend and bot if bot is enabled
2. Run the deployment smoke check.
3. Prepare one test account per role.
4. Confirm that the selected department users and roles exist in the directory.
5. Prepare one rollback contact and one backup copy of the database.

## Users to prepare

Minimum set:

- 1 pilot owner
- 1 department manager / controller
- 2-3 executors
- 1 admin account for support

For each user verify:

- login works
- correct role is assigned
- correct department / unit is assigned
- user sees only the expected data

## Day 1 launch

1. Log in as the manager and create or review the first live task set.
2. Log in as each executor and verify:
   - tasks page opens
   - own tasks are visible
   - task card opens
   - status can be changed
3. Verify the manager can see the result of executor actions.
4. If the bot is enabled:
   - confirm binding works
   - confirm at least one notification path works

## Daily support routine

At the start of each day:

1. Check application health.
2. Confirm the backend service is running.
3. Confirm the frontend opens.
4. Check one real user account login.
5. Check one real task end-to-end.

At the end of each day:

1. Record all pilot issues.
2. Group them into:
   - blocker
   - annoying but workable
   - improvement request
3. Decide which fixes go into the next update.

Use:

- `docs/PILOT_FEEDBACK_TEMPLATE.md` for issue capture
- `docs/PILOT_RELEASE_LOG_TEMPLATE.md` for deployment history
- `docs/PILOT_QM_ROSTER.md` for the first pilot user set

## Feedback format

For each issue capture:

- date
- user
- role
- page / screen
- exact action
- expected result
- actual result
- screenshot if available
- severity

Do not accept vague feedback like "it does not work" without reproducing steps.

## Release rule during pilot

Make small updates only.

For each update record:

- what changed
- whether DB changed
- whether frontend changed
- whether bot changed
- what to test after deployment

Avoid large refactors during the first week of live use.

## Blockers that justify rollback

Rollback or disable the pilot if:

- users cannot log in
- tasks are not visible to the right people
- task status changes are not saved
- data from one department is visible to the wrong users
- bot sends clearly wrong notifications to the wrong users

## Success criteria for week 1

The first week is successful if:

- the pilot group uses the system for one real task flow
- you can deploy one small update without chaos
- user access rules are predictable
- feedback is collected in a structured way
- there are no critical data access incidents

## Week 2 only if week 1 is stable

Only after week 1 is stable:

1. add more users
2. add more departments
3. add more task templates
4. strengthen reporting and analytics
