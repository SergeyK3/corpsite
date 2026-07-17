"use client";

import Link from "next/link";

import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import ApplicantWorkflowStatusBadge from "./ApplicantWorkflowStatusBadge";
import PersonnelApplicationStatusBadge, {
  DirectorResolutionBadge,
} from "./PersonnelApplicationStatusBadge";
import {
  formatPersonnelApplicationDate,
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import {
  intakeDraftStatusLabel,
  intakeLinkStatusBadgeClass,
  intakeLinkStatusLabel,
} from "@/app/intake/_lib/intakeLabels";
import type { PersonnelApplicationListItem } from "../_lib/personnelApplicationsApi.client";

type Props = {
  items: PersonnelApplicationListItem[];
  loading?: boolean;
  archiveMode?: boolean;
  selectedApplicationId?: number | null;
  highlightedApplicationId?: number | null;
  onOpen: (applicationId: number) => void;
  onOpenIntake?: (applicationId: number) => void;
  workflowView?: boolean;
};

function rowClassName(isSelected: boolean, isHighlighted: boolean): string {
  const parts = ["cursor-pointer transition-colors"];
  if (isSelected) {
    parts.push("bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/30 dark:hover:bg-blue-950/40");
  } else if (isHighlighted) {
    parts.push("bg-emerald-50 ring-1 ring-inset ring-emerald-300 hover:bg-emerald-100 dark:bg-emerald-950/30 dark:ring-emerald-800");
  } else {
    parts.push("hover:bg-zinc-50 dark:hover:bg-zinc-900/40");
  }
  return parts.join(" ");
}

export function PersonnelApplicationsTable({
  items,
  loading = false,
  archiveMode = false,
  selectedApplicationId = null,
  highlightedApplicationId = null,
  onOpen,
  onOpenIntake,
  workflowView = false,
}: Props) {
  if (loading) {
    return (
      <div className="space-y-2 p-4" data-testid="personnel-applications-table-skeleton">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-10 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div
        className="rounded-xl border border-dashed border-zinc-300 bg-zinc-50 px-4 py-10 text-center dark:border-zinc-700 dark:bg-zinc-900/40"
        data-testid="personnel-applications-empty"
      >
        <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
          {archiveMode
            ? workflowView
              ? "Архивных претендентов пока нет"
              : "Архивных обращений пока нет"
            : workflowView
              ? "Претендентов пока нет"
              : "Кадровых обращений пока нет"}
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          {archiveMode
            ? "Завершённые, отменённые и просроченные обращения появятся здесь."
            : workflowView
              ? "Зарегистрируйте первого претендента и выдайте ему ссылку на заполнение личной карточки."
              : "Зарегистрируйте первое обращение по бумажному заявлению претендента."}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="personnel-applications-table">
      <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
          <tr>
            <th className="px-4 py-3">ФИО</th>
            <th className="px-4 py-3">ИИН</th>
            <th className="px-4 py-3">Статус</th>
            <th className="px-4 py-3">Сотрудник</th>
            <th className="px-4 py-3">Анкета</th>
            <th className="px-4 py-3">Открыта</th>
            <th className="px-4 py-3">Отправлена</th>
            <th className="px-4 py-3">Дата заявления</th>
            {archiveMode ? <th className="px-4 py-3">Закрыто</th> : null}
            <th className="px-4 py-3" />
            <th className="px-4 py-3">Подразделение</th>
            <th className="px-4 py-3">Должность</th>
            <th className="px-4 py-3">HR</th>
            <th className="px-4 py-3">Регистрация</th>
            <th className="px-4 py-3">Резолюция</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
          {items.map((item) => {
            const isSelected = selectedApplicationId === item.application_id;
            const isHighlighted = highlightedApplicationId === item.application_id;
            return (
              <tr
                key={item.application_id}
                className={rowClassName(isSelected, isHighlighted)}
                onClick={() => onOpen(item.application_id)}
                data-testid={`personnel-application-row-${item.application_id}`}
                data-selected={isSelected ? "true" : "false"}
                data-highlighted={isHighlighted ? "true" : "false"}
                aria-selected={isSelected}
              >
                <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-50">
                  {item.full_name || "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-700 dark:text-zinc-300">
                  {item.iin || "—"}
                </td>
                <td className="px-4 py-3">
                  {workflowView ? (
                    <ApplicantWorkflowStatusBadge
                      status={item.status}
                      intake_link_status={item.intake_link_status}
                      intake_draft_status={item.intake_draft_status}
                    />
                  ) : (
                    <PersonnelApplicationStatusBadge status={item.status} />
                  )}
                </td>
                <td className="px-4 py-3">
                  {item.employee_id != null ? (
                    <Link
                      href={buildEmployeeCardHref(item.employee_id)}
                      className="text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
                      onClick={(e) => e.stopPropagation()}
                      data-testid={`personnel-application-employee-link-${item.application_id}`}
                    >
                      {item.employee_full_name || `#${item.employee_id}`}
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${intakeLinkStatusBadgeClass(item.intake_link_status)}`}
                  >
                    {item.intake_draft_status === "submitted"
                      ? intakeDraftStatusLabel(item.intake_draft_status)
                      : intakeLinkStatusLabel(item.intake_link_status)}
                  </span>
                </td>
                <td className="px-4 py-3">{formatPersonnelApplicationDateTime(item.intake_opened_at)}</td>
                <td className="px-4 py-3">{formatPersonnelApplicationDateTime(item.intake_submitted_at)}</td>
                <td className="px-4 py-3">{formatPersonnelApplicationDate(item.application_received_at)}</td>
                {archiveMode ? (
                  <td className="px-4 py-3">{formatPersonnelApplicationDateTime(item.closed_at)}</td>
                ) : null}
                <td className="px-4 py-3">
                  {!archiveMode && item.intake_draft_status === "submitted" && onOpenIntake ? (
                    <button
                      type="button"
                      className="text-sm text-blue-700 hover:underline dark:text-blue-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenIntake(item.application_id);
                      }}
                      data-testid={`open-intake-button-${item.application_id}`}
                    >
                      Открыть анкету
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">{item.intended_org_unit_name || item.intended_org_group_name || "—"}</td>
                <td className="px-4 py-3">{item.intended_position_name || "—"}</td>
                <td className="px-4 py-3">{item.registered_by_name || `#${item.registered_by_user_id}`}</td>
                <td className="px-4 py-3">{formatPersonnelApplicationDateTime(item.registered_at)}</td>
                <td className="px-4 py-3">
                  <DirectorResolutionBadge status={item.director_resolution_status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
