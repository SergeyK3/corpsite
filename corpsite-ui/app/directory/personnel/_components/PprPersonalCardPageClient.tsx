"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { PERSONAL_CARD_TITLE } from "@/lib/personnelCardTerminology";
import { PPR_CARD_RETURN_HREF } from "@/lib/pprCardFeature";
import {
  PPR_CARD_DEFAULT_SECTION,
  parsePprCardSection,
  type PprCardSectionId,
} from "@/lib/pprCardSections";
import { getPprByEmployeeId } from "../_lib/pprQueryApi.client";
import {
  PPR_LIFECYCLE_NOT_MATERIALIZED,
  PPR_SECTION_CODE_EDUCATION,
  PPR_SECTION_CODE_TRAINING,
  type PprCompositeReadResponse,
  type PprEducationRecordResponse,
  type PprTrainingRecordResponse,
} from "../_lib/pprQueryTypes";
import { mapPprCardError, lifecycleStatusLabel, hrRelationshipLabel } from "../_lib/pprCardPresentation";
import { EmployeeImportCardSection } from "./EmployeeImportCardSection";
import { PprCardSectionNav } from "./PprCardSectionNav";
import PprCardGeneralSection from "./PprCardGeneralSection";
import PprCardEducationSection from "./PprCardEducationSection";
import PprCardTrainingSection from "./PprCardTrainingSection";
import PprCardEventHistorySection from "./PprCardEventHistorySection";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
import EmployeeCardOrdersSection from "./EmployeeCardOrdersSection";

type Props = {
  employeeId: string;
};

function isEducationRecord(
  record: PprEducationRecordResponse | PprTrainingRecordResponse,
): record is PprEducationRecordResponse {
  return "education_kind" in record;
}

export default function PprPersonalCardPageClient({ employeeId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSection = parsePprCardSection(searchParams.get("section"));

  const [loading, setLoading] = React.useState(true);
  const [errorView, setErrorView] = React.useState<ReturnType<typeof mapPprCardError> | null>(null);
  const [ppr, setPpr] = React.useState<PprCompositeReadResponse | null>(null);
  const scrolledSectionRef = React.useRef<PprCardSectionId | null>(null);

  const loadCard = React.useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setErrorView(null);
      try {
        const data = await getPprByEmployeeId(employeeId, { signal });
        setPpr(data);
      } catch (e) {
        if (signal?.aborted) return;
        setPpr(null);
        setErrorView(mapPprCardError(e));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [employeeId],
  );

  React.useEffect(() => {
    const controller = new AbortController();
    void loadCard(controller.signal);
    return () => controller.abort();
  }, [loadCard]);

  React.useEffect(() => {
    if (loading || errorView || !ppr) return;
    if (scrolledSectionRef.current === initialSection) return;
    scrolledSectionRef.current = initialSection;
    const targetId = initialSection === PPR_CARD_DEFAULT_SECTION ? "general" : initialSection;
    const timer = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loading, errorView, ppr, initialSection]);

  const educationSection = ppr?.sections[PPR_SECTION_CODE_EDUCATION];
  const trainingSection = ppr?.sections[PPR_SECTION_CODE_TRAINING];
  const educationActive = (educationSection?.active ?? []).filter(isEducationRecord);
  const educationSuperseded = (educationSection?.superseded ?? []).filter(isEducationRecord);
  const educationVoided = (educationSection?.voided ?? []).filter(isEducationRecord);
  const trainingActive = (trainingSection?.active ?? []).filter(
    (r): r is PprTrainingRecordResponse => !isEducationRecord(r),
  );
  const trainingSuperseded = (trainingSection?.superseded ?? []).filter(
    (r): r is PprTrainingRecordResponse => !isEducationRecord(r),
  );
  const trainingVoided = (trainingSection?.voided ?? []).filter(
    (r): r is PprTrainingRecordResponse => !isEducationRecord(r),
  );

  const displayName = ppr?.general.full_name || `Сотрудник #${employeeId}`;
  const notMaterialized =
    ppr != null &&
    (!ppr.materialization.materialized ||
      ppr.materialization.lifecycle_state === PPR_LIFECYCLE_NOT_MATERIALIZED);

  return (
    <div className="flex max-h-[calc(100dvh-8.5rem)] min-h-[min(100dvh-8.5rem,640px)] flex-col overflow-hidden">
      <div className="shrink-0 border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{PERSONAL_CARD_TITLE}</h1>
            <p className="mt-0.5 text-sm text-zinc-700 dark:text-zinc-300">{displayName}</p>
            {ppr ? (
              <p className="mt-1 text-xs text-zinc-500">
                {lifecycleStatusLabel(ppr.materialization.materialized, ppr.materialization.lifecycle_state)}
                {" · "}
                {hrRelationshipLabel(ppr.materialization.hr_relationship_context)}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => router.push(PPR_CARD_RETURN_HREF)}
            className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
          >
            Назад к персоналу
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {errorView ? (
          <div
            className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
              errorView.kind === "access_denied" || errorView.kind === "not_found"
                ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100"
                : "border-red-200 bg-red-50 text-red-700 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200"
            }`}
          >
            <p>{errorView.message}</p>
            {errorView.retryable ? (
              <button
                type="button"
                className="mt-2 rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
                onClick={() => void loadCard()}
              >
                Повторить
              </button>
            ) : null}
          </div>
        ) : null}

        {loading ? (
          <div className="py-16 text-center text-sm text-zinc-500">Загрузка личной карточки…</div>
        ) : null}

        {ppr && !loading ? (
          <>
            {ppr.metadata.merge_redirected ? (
              <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100">
                Отображаются сведения канонической записи после объединения персональных данных.
              </div>
            ) : null}

            {notMaterialized ? (
              <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100">
                Данные сотрудника доступны. Формирование служебной части личной карточки ещё не завершено.
              </div>
            ) : null}

            <PprCardSectionNav />

            <div className="space-y-5">
              <EmployeeImportCardSection
                id="general"
                title="Общие сведения"
                description="Основные персональные и кадровые сведения."
              >
                <PprCardGeneralSection ppr={ppr} />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="education"
                title="Образование"
                description="Сведения об образовании из личной карточки."
              >
                <PprCardEducationSection
                  active={educationActive}
                  superseded={educationSuperseded}
                  voided={educationVoided}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="training"
                title="Обучение и повышение квалификации"
                description="Сведения о профессиональном обучении."
              >
                <PprCardTrainingSection
                  active={trainingActive}
                  superseded={trainingSuperseded}
                  voided={trainingVoided}
                />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="assignment"
                title="Трудовая деятельность"
                description="Текущее назначение и операционный контур занятости."
              >
                <EmployeeOperationalAssignmentSection employeeId={employeeId} batchId={null} rowId={null} />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="orders"
                title="Кадровые приказы"
                description="Юридически значимые кадровые действия."
              >
                <EmployeeCardOrdersSection employeeId={employeeId} />
              </EmployeeImportCardSection>

              <EmployeeImportCardSection
                id="changes"
                title="История изменений"
                description="Краткая хронология событий личной карточки."
              >
                <PprCardEventHistorySection events={ppr.events} />
              </EmployeeImportCardSection>

              {ppr.identity.employee_context_id != null ? (
                <p className="text-xs text-zinc-500">
                  Кадровый контекст: сотрудник #{ppr.identity.employee_context_id}
                  {ppr.identity.resolved_person_id
                    ? ` · person #${ppr.identity.resolved_person_id}`
                    : ""}
                </p>
              ) : null}

              <p className="text-xs text-zinc-500">
                <button
                  type="button"
                  className="underline-offset-2 hover:underline"
                  onClick={() => void loadCard()}
                >
                  Обновить данные
                </button>
              </p>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
