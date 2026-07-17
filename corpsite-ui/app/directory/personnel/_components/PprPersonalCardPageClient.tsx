"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { PERSONAL_CARD_TITLE } from "@/lib/personnelCardTerminology";
import { parseReturnToFromSearchParams } from "@/lib/taskNav";
import {
  isPersonnelApplicationsJournalReturnHref,
  resolvePersonalCardBackHref,
  resolvePersonnelApplicationsJournalBackLabel,
} from "../_lib/personnelApplicationsJournalNav";
import {
  canCreateHireOrderFromApplicantCard,
} from "../_lib/personnelApplicantWorkflow";
import {
  getPersonApplicationsHistory,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";
import {
  PPR_CARD_DEFAULT_SECTION,
  PPR_CARD_SECTIONS,
  parsePprCardSection,
  type PprCardSectionId,
} from "@/lib/pprCardSections";
import { getPprByEmployeeId, getPprByPersonId } from "../_lib/pprQueryApi.client";
import {
  PPR_HR_RELATIONSHIP_CANDIDATE,
  PPR_LIFECYCLE_NOT_MATERIALIZED,
  PPR_SECTION_CODE_EDUCATION,
  PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
  PPR_SECTION_CODE_FAMILY,
  PPR_SECTION_CODE_MILITARY,
  PPR_SECTION_CODE_TRAINING,
  type PprCompositeReadResponse,
  type PprEducationRecordResponse,
  type PprExternalEmploymentRecordResponse,
  type PprIntendedEmploymentResponse,
  type PprMilitaryRecordResponse,
  type PprRelativeRecordResponse,
  type PprSectionRecordResponse,
  type PprTrainingRecordResponse,
} from "../_lib/pprQueryTypes";
import { mapPprCardError, lifecycleStatusLabel, hrRelationshipLabel } from "../_lib/pprCardPresentation";
import type { PprEmploymentBiographyRoute, PprMilitaryServiceRoute } from "../_lib/pprCommandApi.client";
import { EmployeeImportCardSection } from "./EmployeeImportCardSection";
import { PprCardSectionNav } from "./PprCardSectionNav";
import PprCardGeneralSection from "./PprCardGeneralSection";
import PprCardEducationSection from "./PprCardEducationSection";
import PprCardTrainingSection from "./PprCardTrainingSection";
import PprCardFamilySection from "./PprCardFamilySection";
import PprCardMilitarySection from "./PprCardMilitarySection";
import PprCardEmploymentBiographySection from "./PprCardEmploymentBiographySection";
import PprCardEventHistorySection from "./PprCardEventHistorySection";
import PprCardIntendedEmploymentSection from "./PprCardIntendedEmploymentSection";
import PprCardApplicationsSection from "./PprCardApplicationsSection";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
import EmployeeCardOrdersSection from "./EmployeeCardOrdersSection";
import EmployeeOnboardingSection from "./EmployeeOnboardingSection";

type Props = {
  employeeId?: string;
  personId?: string;
  /** When false, PPR section mutations stay hidden while records remain visible. */
  canEditPprSections?: boolean;
};

function isEducationRecord(record: PprSectionRecordResponse): record is PprEducationRecordResponse {
  return "education_kind" in record;
}

function isRelativeRecord(record: PprSectionRecordResponse): record is PprRelativeRecordResponse {
  return "relationship_type" in record;
}

function isExternalEmploymentRecord(
  record: PprSectionRecordResponse,
): record is PprExternalEmploymentRecordResponse {
  return "source_system" in record && "record_kind" in record;
}

function isMilitaryRecord(record: PprSectionRecordResponse): record is PprMilitaryRecordResponse {
  return "source_type" in record && !("source_system" in record);
}

export default function PprPersonalCardPageClient({
  employeeId,
  personId,
  canEditPprSections = true,
}: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSection = parsePprCardSection(searchParams.get("section"));
  const returnToHref = React.useMemo(
    () => resolvePersonalCardBackHref(parseReturnToFromSearchParams(searchParams)),
    [searchParams],
  );
  const backToJournal = isPersonnelApplicationsJournalReturnHref(returnToHref);
  const backButtonLabel = backToJournal
    ? resolvePersonnelApplicationsJournalBackLabel(returnToHref)
    : "Назад к персоналу";

  const [loading, setLoading] = React.useState(true);
  const [errorView, setErrorView] = React.useState<ReturnType<typeof mapPprCardError> | null>(null);
  const [ppr, setPpr] = React.useState<PprCompositeReadResponse | null>(null);
  const [intendedEmployment, setIntendedEmployment] = React.useState<PprIntendedEmploymentResponse | null>(null);
  const [activeApplication, setActiveApplication] = React.useState<PersonnelApplicationDetail | null>(null);
  const scrolledSectionRef = React.useRef<PprCardSectionId | null>(null);

  const resolvedPersonId = ppr?.identity.resolved_person_id ?? (personId ? Number(personId) : null);
  const resolvedEmployeeId =
    ppr?.identity.employee_context_id != null
      ? String(ppr.identity.employee_context_id)
      : employeeId ?? null;

  const loadCard = React.useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setErrorView(null);
      try {
        const data =
          personId != null
            ? await getPprByPersonId(personId, { signal })
            : await getPprByEmployeeId(String(employeeId), { signal });
        setPpr(data);
        setIntendedEmployment(data.intended_employment);
      } catch (e) {
        if (signal?.aborted) return;
        setPpr(null);
        setIntendedEmployment(null);
        setErrorView(mapPprCardError(e));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [employeeId, personId],
  );

  React.useEffect(() => {
    const controller = new AbortController();
    void loadCard(controller.signal);
    return () => controller.abort();
  }, [loadCard]);

  React.useEffect(() => {
    if (resolvedPersonId == null) {
      setActiveApplication(null);
      return;
    }
    let cancelled = false;
    void getPersonApplicationsHistory(resolvedPersonId)
      .then((body) => {
        if (cancelled) return;
        const items = Array.isArray(body.items) ? body.items : [];
        const active =
          items.find((item) => !item.is_read_only && item.status !== "completed") ?? items[0] ?? null;
        setActiveApplication(active);
      })
      .catch(() => {
        if (!cancelled) setActiveApplication(null);
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedPersonId]);

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
  const familySection = ppr?.sections[PPR_SECTION_CODE_FAMILY];
  const militarySection = ppr?.sections[PPR_SECTION_CODE_MILITARY];
  const employmentBiographySection = ppr?.sections[PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY];
  const educationActive = (educationSection?.active ?? []).filter(isEducationRecord);
  const educationSuperseded = (educationSection?.superseded ?? []).filter(isEducationRecord);
  const educationVoided = (educationSection?.voided ?? []).filter(isEducationRecord);
  const trainingActive = (trainingSection?.active ?? []).filter(
    (r): r is PprTrainingRecordResponse =>
      !isEducationRecord(r) && !isRelativeRecord(r) && !isExternalEmploymentRecord(r) && !isMilitaryRecord(r),
  );
  const trainingSuperseded = (trainingSection?.superseded ?? []).filter(
    (r): r is PprTrainingRecordResponse =>
      !isEducationRecord(r) && !isRelativeRecord(r) && !isExternalEmploymentRecord(r) && !isMilitaryRecord(r),
  );
  const trainingVoided = (trainingSection?.voided ?? []).filter(
    (r): r is PprTrainingRecordResponse =>
      !isEducationRecord(r) && !isRelativeRecord(r) && !isExternalEmploymentRecord(r) && !isMilitaryRecord(r),
  );
  const familyActive = (familySection?.active ?? []).filter(isRelativeRecord);
  const familySuperseded = (familySection?.superseded ?? []).filter(isRelativeRecord);
  const familyVoided = (familySection?.voided ?? []).filter(isRelativeRecord);
  const militaryActive = (militarySection?.active ?? []).filter(isMilitaryRecord);
  const militarySuperseded = (militarySection?.superseded ?? []).filter(isMilitaryRecord);
  const militaryVoided = (militarySection?.voided ?? []).filter(isMilitaryRecord);
  const employmentBiographyActive = (employmentBiographySection?.active ?? []).filter(isExternalEmploymentRecord);
  const employmentBiographySuperseded = (employmentBiographySection?.superseded ?? []).filter(isExternalEmploymentRecord);
  const employmentBiographyVoided = (employmentBiographySection?.voided ?? []).filter(isExternalEmploymentRecord);

  const displayName =
    ppr?.general.full_name ||
    (personId ? `Заявитель #${personId}` : `Сотрудник #${employeeId}`);
  const isApplicant = ppr?.materialization.hr_relationship_context === PPR_HR_RELATIONSHIP_CANDIDATE;
  const canCreateHireOrder =
    isApplicant &&
    resolvedPersonId != null &&
    activeApplication != null &&
    canCreateHireOrderFromApplicantCard(activeApplication.status);
  const visibleCardSections = React.useMemo(
    () =>
      PPR_CARD_SECTIONS.filter((section) => {
        if (section.id === "onboarding") return !isApplicant && resolvedEmployeeId != null;
        if (section.id === "intended_employment") return isApplicant;
        if (section.id === "assignment" || section.id === "orders") {
          return !isApplicant && resolvedEmployeeId != null;
        }
        return true;
      }),
    [isApplicant, resolvedEmployeeId],
  );
  const notMaterialized =
    ppr != null &&
    (!ppr.materialization.materialized ||
      ppr.materialization.lifecycle_state === PPR_LIFECYCLE_NOT_MATERIALIZED);
  const employmentBiographyEditable = !notMaterialized && canEditPprSections;
  const militaryEditable = !notMaterialized && canEditPprSections;

  const employmentBiographyRoute: PprEmploymentBiographyRoute | null =
    personId != null
      ? { kind: "person", id: Number(personId) }
      : resolvedEmployeeId != null
        ? { kind: "employee", id: resolvedEmployeeId }
        : null;

  const militaryRoute: PprMilitaryServiceRoute | null =
    personId != null
      ? { kind: "person", id: Number(personId) }
      : resolvedEmployeeId != null
        ? { kind: "employee", id: resolvedEmployeeId }
        : null;

  return (
    <div className="flex max-h-[calc(100dvh-8.5rem)] min-h-[min(100dvh-8.5rem,640px)] flex-col overflow-hidden">
      <div
        className={`shrink-0 border-b px-4 py-3 sm:px-6 ${
          isApplicant
            ? "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40"
            : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {isApplicant ? (
              <p
                className="text-xs font-bold uppercase tracking-[0.14em] text-amber-900 dark:text-amber-100"
                data-testid="ppr-applicant-status-banner"
              >
                Заявитель
              </p>
            ) : null}
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{PERSONAL_CARD_TITLE}</h1>
            <p className="mt-0.5 text-sm text-zinc-700 dark:text-zinc-300">{displayName}</p>
            {ppr ? (
              <p className="mt-1 text-xs text-zinc-500">
                Статус: {hrRelationshipLabel(ppr.materialization.hr_relationship_context)}
                {" · "}
                {lifecycleStatusLabel(ppr.materialization.materialized, ppr.materialization.lifecycle_state)}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => router.push(returnToHref)}
            className="rounded border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
            data-testid="ppr-card-back-button"
          >
            {backButtonLabel}
          </button>
          {canCreateHireOrder ? (
            <button
              type="button"
              onClick={() =>
                router.push(
                  `/directory/personnel/orders?create=1&hire_person_id=${resolvedPersonId}&order_type=HIRE`,
                )
              }
              className="rounded border border-amber-400 bg-amber-100 px-4 py-2 text-sm font-medium text-amber-950 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-50"
              data-testid="ppr-applicant-create-hire-order"
            >
              Создать приказ о приёме
            </button>
          ) : null}
        </div>
        {isApplicant ? (
          <p className="mt-2 text-sm text-amber-900 dark:text-amber-100">
            {canCreateHireOrder
              ? "Личная карточка заполнена. Можно перейти к оформлению приказа о приёме."
              : "Трудовые отношения ещё не оформлены. Приказ о приёме станет доступен после отправки анкеты претендентом."}
          </p>
        ) : null}
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

            <PprCardSectionNav sections={visibleCardSections} />

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
                id="family"
                title="Родственники"
                description="Сведения о близких родственниках."
              >
                <PprCardFamilySection
                  active={familyActive}
                  superseded={familySuperseded}
                  voided={familyVoided}
                />
              </EmployeeImportCardSection>

              {militaryRoute ? (
                <EmployeeImportCardSection
                  id="military"
                  title="Воинский учёт"
                  description="Сведения о воинской обязанности и воинском учёте."
                >
                  <PprCardMilitarySection
                    active={militaryActive}
                    superseded={militarySuperseded}
                    voided={militaryVoided}
                    route={militaryRoute}
                    editable={militaryEditable}
                    onMutated={() => loadCard()}
                  />
                </EmployeeImportCardSection>
              ) : null}

              {employmentBiographyRoute ? (
                <EmployeeImportCardSection
                  id="employment_biography"
                  title="Трудовая биография"
                  description="Сведения о трудовой деятельности до поступления в организацию."
                >
                  <PprCardEmploymentBiographySection
                    active={employmentBiographyActive}
                    superseded={employmentBiographySuperseded}
                    voided={employmentBiographyVoided}
                    route={employmentBiographyRoute}
                    editable={employmentBiographyEditable}
                    onMutated={() => loadCard()}
                  />
                </EmployeeImportCardSection>
              ) : null}

              {isApplicant && resolvedPersonId != null ? (
                <EmployeeImportCardSection
                  id="intended_employment"
                  title="Предполагаемое трудоустройство"
                  description="Намерение работодателя о подразделении, должности и ставке до приказа о приёме."
                >
                  <PprCardIntendedEmploymentSection
                    personId={resolvedPersonId}
                    initial={intendedEmployment}
                    onSaved={(value) => setIntendedEmployment(value)}
                  />
                </EmployeeImportCardSection>
              ) : null}

              {!isApplicant && resolvedEmployeeId ? (
                <EmployeeImportCardSection
                  id="assignment"
                  title="Трудовая деятельность"
                  description="Текущее назначение и операционный контур занятости."
                >
                  <EmployeeOperationalAssignmentSection
                    employeeId={resolvedEmployeeId}
                    batchId={null}
                    rowId={null}
                  />
                </EmployeeImportCardSection>
              ) : null}

              {!isApplicant && resolvedEmployeeId ? (
                <EmployeeImportCardSection
                  id="orders"
                  title="Кадровые приказы"
                  description="Юридически значимые кадровые действия."
                >
                  <EmployeeCardOrdersSection employeeId={resolvedEmployeeId} />
                </EmployeeImportCardSection>
              ) : null}

              {!isApplicant && resolvedEmployeeId ? (
                <EmployeeImportCardSection
                  id="onboarding"
                  title="Адаптация"
                  description="Чек-лист адаптации нового сотрудника."
                >
                  <EmployeeOnboardingSection employeeId={resolvedEmployeeId} />
                </EmployeeImportCardSection>
              ) : null}

              {resolvedPersonId != null ? (
                <EmployeeImportCardSection
                  id="applications"
                  title="Кадровые обращения"
                  description="История кадровых обращений по бумажным заявлениям."
                >
                  <PprCardApplicationsSection personId={resolvedPersonId} />
                </EmployeeImportCardSection>
              ) : null}

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
              ) : resolvedPersonId != null ? (
                <p className="text-xs text-zinc-500">Кадровый контекст: person #{resolvedPersonId}</p>
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
