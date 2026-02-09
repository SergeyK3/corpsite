// FILE: corpsite-ui/lib/types.ts

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
  executor_role_id?: number;
  assignment_scope?: string;

  status_id?: number;
  status_code?: string;
  status_name_ru?: string;

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
  executor_role_id?: number;
  assignment_scope?: string;

  status_id?: number;
  status_code?: string;
  status_name_ru?: string;

  // legacy/optional
  status?: string;
  deadline?: string | null;

  // accept backend shapes
  allowed_actions?: AllowedActionsRaw;
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
