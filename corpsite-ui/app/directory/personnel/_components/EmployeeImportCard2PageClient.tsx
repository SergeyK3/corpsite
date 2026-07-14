"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { HR_PROCESSES_NAV_HREF } from "@/lib/personnelNav";
import {
  EMPLOYEE_CARD_DEFAULT_SECTION,
  parseEmployeeCardSection,
  type EmployeeCardSectionId,
} from "@/lib/employeeCardNav";
import { getEmployee, mapApiErrorToMessage } from "../../employees/_lib/api.client";
import type { EmployeeDetails } from "../../employees/_lib/types";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
import EmployeePersonnelHistorySection from "./EmployeePersonnelHistorySection";
import EmployeeCardGeneralSection from "./EmployeeCardGeneralSection";
import EmployeeCardOrdersSection from "./EmployeeCardOrdersSection";
import EmployeeCardDeletionNotice from "./EmployeeCardDeletionNotice";
import { EmployeeImportCardSection, EmployeeImportCardSectionNav } from "./EmployeeImportCardSection";
import EmployeeAccountSections from "../../employees/_components/EmployeeAccountSections";
import {
  getEmployeeImportCard2Optional,
  type EmployeeImportCard2Detail,
} from "../_lib/importApi.client";

type Props = {
  employeeId: string;
};

function displayNameFromEmployee(details: EmployeeDetails | null, employeeId: string): string {
  if (!details) return "—";
  const d = details as Record<string, unknown>;
  return String(d.fio ?? d.full_name ?? d.fullName ?? "").trim() || `Сотрудник #${employeeId}`;
}

export default function EmployeeImportCard2PageClient({ employeeId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const provisionAccount = searchParams.get("provisionAccount") === "1";
  const initialSection = parseEmployeeCardSection(searchParams.get("section"));

  const [shellLoading, setShellLoading] = React.useState(true);
  const [shellError, setShellError] = React.useState<string | null>(null);
  const [employee, setEmployee] = React.useState<EmployeeDetails | null>(null);
  const [importDetail, setImportDetail] = React.useState<EmployeeImportCard2Detail | null>(null);
  const [assignmentRefreshToken, setAssignmentRefreshToken] = React.useState(0);
  const scrolledSectionRef = React.useRef<EmployeeCardSectionId | null>(null);

  const loadShell = React.useCallback(async () => {
    setShellLoading(true);
    setShellError(null);
    try {
      const [employeeData, importData] = await Promise.all([
        getEmployee(employeeId),
        getEmployeeImportCard2Optional(employeeId),
      ]);
      setEmployee(employeeData);
      setImportDetail(importData);
    } catch (e) {
      setEmployee(null);
      setImportDetail(null);
      setShellError(mapApiErrorToMessage(e, "Не удалось загрузить карточку сотрудника."));
    } finally {
      setShellLoading(false);
    }
  }, [employeeId]);

  React.useEffect(() => {
    void loadShell();
  }, [loadShell]);

  React.useEffect(() => {
    if (shellLoading || shellError || !employee) return;
    if (scrolledSectionRef.current === initialSection) return;
    scrolledSectionRef.current = initialSection;

    const targetId = initialSection === EMPLOYEE_CARD_DEFAULT_SECTION ? "assignment" : initialSection;
    const timer = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [shellLoading, shellError, employee, initialSection]);

  function handleClose() {
    router.push(HR_PROCESSES_NAV_HREF);
  }

  const displayName = displayNameFromEmployee(employee, employeeId);
  const hasImportRow = importDetail != null;

  return (
    <div className="flex max-h-[calc(100dvh-8.5rem)] min-h-[min(100dvh-8.5rem,640px)] flex-col overflow-hidden">
      <div className="shrink-0 border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{displayName}</h1>
            <p className="mt-0.5 text-xs text-zinc-500">Карточка сотрудника</p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {importDetail?.missing_from_latest_import ? (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
            Сотрудник отсутствует в последней HR-выгрузке (batch #{importDetail.latest_batch_id ?? "—"}).
            Данные импорта могут быть устаревшими.
          </div>
        ) : null}

        {!hasImportRow && !shellLoading && !shellError && employee ? (
          <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100">
            Кадровое портфолио не привязано к HR-импорту. Операционные разделы карточки доступны.
          </div>
        ) : null}

        {shellError ? (
          <div className="mb-4 whitespace-pre-wrap rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
            {shellError}
          </div>
        ) : null}

        {shellLoading ? (
          <div className="py-16 text-center text-sm text-zinc-500">Загрузка карточки сотрудника…</div>
        ) : employee ? (
          <>
            <EmployeeImportCardSectionNav />

            <div className="space-y-5">
              <EmployeeImportCardSection
                id="general"
                title="Общие сведения"
                description="Идентификация сотрудника и статус в справочнике персонала."
              >
                <EmployeeCardGeneralSection
                  employeeId={employeeId}
                  details={employee}
                  onDetailsChanged={() => {
                    void loadShell();
                    setAssignmentRefreshToken((t) => t + 1);
                  }}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="assignment"
                title="Текущее назначение"
                description="Организационное назначение в справочнике персонала. Кадровые изменения — через приказы."
              >
                <EmployeeOperationalAssignmentSection
                  employeeId={employeeId}
                  batchId={importDetail?.batch_id ?? null}
                  rowId={importDetail?.row_id ?? null}
                  refreshToken={assignmentRefreshToken}
                  onAssignmentChanged={() => setAssignmentRefreshToken((t) => t + 1)}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="access"
                title="Доступ"
                description="Учётная запись Corpsite и каналы уведомлений. Отделено от кадрового контура."
              >
                <EmployeeAccountSections
                  employeeId={employeeId}
                  initialUserCreateOpen={provisionAccount}
                  refreshToken={assignmentRefreshToken}
                  embedded
                  showEvents={false}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="orders"
                title="Кадровые приказы"
                description="Юридически значимые кадровые действия оформляются только через приказы."
              >
                <EmployeeCardOrdersSection employeeId={employeeId} />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="history"
                title="История кадровых событий"
                description="Хронология кадровых событий и связанных приказов. Только просмотр."
              >
                <EmployeePersonnelHistorySection
                  employeeId={employeeId}
                  refreshToken={assignmentRefreshToken}
                />
              </EmployeeImportCardSection>

              <EmployeeCardDeletionNotice />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
