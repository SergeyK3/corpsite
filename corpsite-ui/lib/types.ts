export type AllowedAction = "report" | "approve" | "reject";

export type TaskListItem = {
  task_id: number;
  title: string;
  status: string;
  deadline?: string | null;
  allowed_actions?: AllowedAction[] | null;
};

export type TaskDetails = {
  task_id: number;
  title: string;
  description?: string | null;
  status: string;
  deadline?: string | null;
  allowed_actions: AllowedAction[];
};

export type TaskAction = "report" | "approve" | "reject";

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
