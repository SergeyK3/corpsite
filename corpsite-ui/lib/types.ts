// FILE: corpsite-ui/lib/types.ts

export type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_code?: string;
  role_name_ru?: string;
  role_name?: string;
  full_name?: string;
  login?: string;
  is_active?: boolean;
  unit_id?: number;
  telegram_bound?: boolean;
  telegram_username?: string | null;
  /** From GET /auth/me — backend is_privileged() (role_id=2 or env allowlist). */
  is_privileged?: boolean;
  is_system_admin?: boolean;
  /** Sysadmin cabinet API (/admin/users, /admin/access/*, …) — not directory privileged roles. */
  has_sysadmin_api?: boolean;
  /** ADR-043 C4.2 — personnel lifecycle admin (ADMIN or HR_ENROLLMENT_MANAGER). */
  has_personnel_admin?: boolean;
  /** ADR-043 C4.2 — override approve/reject (ADMIN or HR_ENROLLMENT_MANAGER). */
  has_hr_governance?: boolean;
  /** ADR-042 E1 — personnel directory / org sidebar visibility. */
  has_personnel_visibility?: boolean;
  show_org_sidebar?: boolean;
  personnel_visibility?: PersonnelVisibilityInfo;
  /** GET /auth/me — backend can_view_team_tasks(); controls «Все задачи» tab visibility. */
  can_view_all_tasks?: boolean;
};

export type PersonnelVisibilityInfo = {
  organization_wide?: boolean;
  scope_unit_ids?: number[] | null;
  can_view_personnel?: boolean;
  can_view_tasks?: boolean;
  source?: string;
  matched_assignment_ids?: number[];
  implicit_from_access_level?: boolean;
};

export type TelegramBindCodeResponse = {
  code: string;
  expires_at: string;
};

export type TaskScope = "mine" | "team";

// UI actions we show as buttons
export type AllowedAction = "report" | "approve" | "reject" | "archive";

// Backend may return allowed_actions as:
// - object: { "archive": true }
// - list:   ["archive"]
// - empty object / empty list / null
export type AllowedActionsRaw = Record<string, any> | string[] | null | undefined;

export type TaskListItem = {
  task_id: number;
  period_id?: number;
  regular_task_id?: number | null;
  title: string;
  description?: string | null;

  initiator_user_id?: number;
  created_by_user_id?: number | null;
  approver_user_id?: number | null;

  executor_role_id?: number;
  executor_user_id?: number | null;
  executor_name?: string | null;

  assignment_scope?: string;

  status_id?: number;
  status_code?: string;
  status_name_ru?: string;

  task_kind?: string | null;
  schedule_type?: string | null;
  requires_report?: boolean;
  requires_approval?: boolean;
  source_kind?: string | null;
  source_note?: string | null;

  due_date?: string | null;

  report_link?: string | null;
  report_submitted_at?: string | null;
  report_submitted_by?: number | null;
  report_submitted_by_role_name?: string | null;
  report_submitted_by_role_code?: string | null;

  report_approved_at?: string | null;
  report_approved_by?: number | null;
  report_current_comment?: string | null;

  // legacy/optional
  status?: string;
  deadline?: string | null;

  // accept backend shapes
  allowed_actions?: AllowedActionsRaw;
};

export type TaskDetails = {
  task_id: number;
  period_id?: number;
  regular_task_id?: number | null;
  title: string;
  description?: string | null;

  initiator_user_id?: number;
  created_by_user_id?: number | null;
  approver_user_id?: number | null;

  executor_role_id?: number;
  executor_user_id?: number | null;
  executor_name?: string | null;

  assignment_scope?: string;

  status_id?: number;
  status_code?: string;
  status_name_ru?: string;

  task_kind?: string | null;
  schedule_type?: string | null;
  requires_report?: boolean;
  requires_approval?: boolean;
  source_kind?: string | null;
  source_note?: string | null;

  due_date?: string | null;

  report_link?: string | null;
  report_submitted_at?: string | null;
  report_submitted_by?: number | null;
  report_submitted_by_role_name?: string | null;
  report_submitted_by_role_code?: string | null;

  report_approved_at?: string | null;
  report_approved_by?: number | null;
  report_current_comment?: string | null;

  // legacy/optional
  status?: string;
  deadline?: string | null;

  // accept backend shapes
  allowed_actions?: AllowedActionsRaw;
};

export type TasksListResponse = {
  scope?: TaskScope;
  total?: number;
  limit?: number;
  offset?: number;
  items?: TaskListItem[];
};

export type TaskAction = AllowedAction;

export type TaskActionPayload = {
  report_link?: string;
  current_comment?: string;

  // approve/reject/archive
  reason?: string;
};

export type RegularTaskStatus = "active" | "inactive" | "all";

export type RegularTask = {
  regular_task_id: number;

  code?: string | null;
  title: string;
  description?: string | null;

  is_active?: boolean;

  schedule_type?: string | null;
  schedule_params?: any;

  create_offset_days?: number;
  due_offset_days?: number;

  executor_role_id?: number | null;
  assignment_scope?: string | null;

  created_by_user_id?: number | null;
  updated_at?: string | null;
};

export type RegularTasksListResponse = {
  total?: number;
  limit?: number;
  offset?: number;
  items?: RegularTask[];
};

export type APIError = {
  status: number;
  code?: string;
  message?: string;
  details?: any;
};