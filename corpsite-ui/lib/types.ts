// FILE: corpsite-ui/lib/types.ts
export type AllowedAction = "report" | "approve" | "reject" | "archive";

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

  allowed_actions?: AllowedAction[] | null;
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

  allowed_actions: AllowedAction[];
};

export type TaskAction = "report" | "approve" | "reject" | "archive";

export type TaskActionPayload = {
  report_link?: string;
  current_comment?: string;
};

export type APIError = {
  status: number;
  code?: string;
  message?: string;
  details?: any;
};
