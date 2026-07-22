"use client";

import Link from "next/link";

import { buildPersonCardHref } from "@/lib/employeeCardNav";
import ApplicantIntakeLinkTableCell from "./ApplicantIntakeLinkTableCell";
import ApplicantWorkflowStatusBadge from "./ApplicantWorkflowStatusBadge";
import { DirectorResolutionBadge } from "./PersonnelApplicationStatusBadge";
import {
  formatPersonnelApplicationDate,
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import type { PersonnelApplicationListItem } from "../_lib/personnelApplicationsApi.client";

type Props = {
  items: PersonnelApplicationListItem[];
  loading?: boolean;
  archiveMode?: boolean;
  selectedApplicationId?: number | null;
  highlightedApplicationId?: number | null;
  onOpen: (applicationId: number) => void;
  onOpenIntake?: (applicationId: number) => void;
};

const TABLE_HEAD_CLASS =
  "px-3 py-2 align-bottom text-left text-[11px] font-medium leading-snug tracking-normal text-zinc-600 break-words whitespace-normal dark:text-zinc-400";
const TABLE_CELL_CLASS = "px-3 py-2 align-top min-w-0 overflow-hidden";
const TABLE_CELL_MONO_CLASS = `${TABLE_CELL_CLASS} font-mono text-[11px] leading-snug text-zinc-700 dark:text-zinc-300`;
const TABLE_CELL_DATE_CLASS = `${TABLE_CELL_CLASS} text-[11px] leading-snug text-zinc-700 break-words dark:text-zinc-300`;

/** Percent widths for table-fixed layout (must sum to 100). */
const ACTIVE_COLUMN_WIDTHS = [
  "9%", // ФИО
  "6%", // ИИН
  "7%", // Статус
  "8%", // Сотрудник
  "12%", // Анкета ЛК
  "6%", // Открыта
  "6%", // Отправлена
  "6%", // Дата заявления
  "8.5%", // Действие
  "12%", // Подразделение
  "8%", // Должность
  "5.5%", // HR
  "6%", // Регистрация
  "7%", // Резолюция
] as const;

const ARCHIVE_COLUMN_WIDTHS = [
  "8.5%", // ФИО
  "5.5%", // ИИН
  "6.5%", // Статус
  "7.5%", // Сотрудник
  "11%", // Анкета ЛК
  "5%", // Открыта
  "5%", // Отправлена
  "5%", // Дата заявления
  "5%", // Закрыто
  "6.5%", // Действие
  "11.5%", // Подразделение
  "7.5%", // Должность
  "5.5%", // HR
  "6%", // Регистрация
  "7%", // Резолюция
] as const;

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

function TableColGroup({ widths }: { widths: readonly string[] }) {
  return (
    <colgroup>
      {widths.map((width, index) => (
        <col key={`${width}-${index}`} style={{ width }} />
      ))}
    </colgroup>
  );
}

export function PersonnelApplicationsTable({
  items,
  loading = false,
  archiveMode = false,
  selectedApplicationId = null,
  highlightedApplicationId = null,
  onOpen,
  onOpenIntake,
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
          {archiveMode ? "Архивных претендентов пока нет" : "Претендентов пока нет"}
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          {archiveMode
            ? "Завершённые, отменённые и просроченные обращения появятся здесь."
            : "Зарегистрируйте первого претендента и выдайте ему ссылку на заполнение личной карточки."}
        </p>
      </div>
    );
  }

  const columnWidths = archiveMode ? ARCHIVE_COLUMN_WIDTHS : ACTIVE_COLUMN_WIDTHS;

  return (
    <div
      className="w-full overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="personnel-applications-table"
    >
      <table className="w-full table-fixed border-collapse text-sm">
        <TableColGroup widths={columnWidths} />
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className={TABLE_HEAD_CLASS}>ФИО</th>
            <th className={TABLE_HEAD_CLASS}>ИИН</th>
            <th className={TABLE_HEAD_CLASS}>Статус</th>
            <th className={TABLE_HEAD_CLASS}>Сотрудник</th>
            <th className={TABLE_HEAD_CLASS}>Анкета ЛК</th>
            <th className={TABLE_HEAD_CLASS}>Открыта</th>
            <th className={TABLE_HEAD_CLASS}>Отправлена</th>
            <th className={TABLE_HEAD_CLASS}>Дата заявления</th>
            {archiveMode ? <th className={TABLE_HEAD_CLASS}>Закрыто</th> : null}
            <th className={TABLE_HEAD_CLASS}>Действие</th>
            <th className={TABLE_HEAD_CLASS}>Подразделение</th>
            <th className={TABLE_HEAD_CLASS}>Должность</th>
            <th className={TABLE_HEAD_CLASS}>HR</th>
            <th className={TABLE_HEAD_CLASS}>Регистрация</th>
            <th className={TABLE_HEAD_CLASS}>Резолюция</th>
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
                <td className={`${TABLE_CELL_CLASS} font-medium text-zinc-900 dark:text-zinc-50`}>
                  <span className="block break-words">{item.full_name || "—"}</span>
                </td>
                <td className={TABLE_CELL_MONO_CLASS}>
                  {item.iin || "—"}
                </td>
                <td className={TABLE_CELL_CLASS}>
                  <ApplicantWorkflowStatusBadge
                    status={item.status}
                    intake_link_status={item.intake_link_status}
                    intake_draft_status={item.intake_draft_status}
                  />
                </td>
                <td className={TABLE_CELL_CLASS}>
                  {item.employee_id != null ? (
                    <Link
                      href={buildPersonCardHref(item.person_id)}
                      className="block break-words text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
                      onClick={(e) => e.stopPropagation()}
                      data-testid={`personnel-application-employee-link-${item.application_id}`}
                    >
                      {item.employee_full_name || `#${item.employee_id}`}
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={TABLE_CELL_CLASS}>
                  <ApplicantIntakeLinkTableCell
                    applicationId={item.application_id}
                    displayState={item.intake_link_display_state}
                    intakeUrlPath={item.intake_url_path}
                    intakeLinkStatus={item.intake_link_status}
                    intakeDraftStatus={item.intake_draft_status}
                  />
                </td>
                <td className={TABLE_CELL_DATE_CLASS}>
                  {formatPersonnelApplicationDateTime(item.intake_opened_at)}
                </td>
                <td className={TABLE_CELL_DATE_CLASS}>
                  {formatPersonnelApplicationDateTime(item.intake_submitted_at)}
                </td>
                <td className={TABLE_CELL_DATE_CLASS}>
                  {formatPersonnelApplicationDate(item.application_received_at)}
                </td>
                {archiveMode ? (
                  <td className={TABLE_CELL_DATE_CLASS}>
                    {formatPersonnelApplicationDateTime(item.closed_at)}
                  </td>
                ) : null}
                <td className={TABLE_CELL_CLASS}>
                  {!archiveMode && item.intake_draft_status === "submitted" && onOpenIntake ? (
                    <button
                      type="button"
                      className="block w-full max-w-full rounded border border-zinc-300 px-1.5 py-1 text-center text-[11px] leading-snug text-blue-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-blue-300 dark:hover:bg-zinc-900"
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
                <td className={`${TABLE_CELL_CLASS} break-words`}>
                  {item.intended_org_unit_name || item.intended_org_group_name || "—"}
                </td>
                <td className={`${TABLE_CELL_CLASS} break-words`}>
                  {item.intended_position_name || "—"}
                </td>
                <td className={`${TABLE_CELL_CLASS} break-words text-xs`}>
                  {item.registered_by_name || `#${item.registered_by_user_id}`}
                </td>
                <td className={TABLE_CELL_DATE_CLASS}>
                  {formatPersonnelApplicationDateTime(item.registered_at)}
                </td>
                <td className={TABLE_CELL_CLASS}>
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
