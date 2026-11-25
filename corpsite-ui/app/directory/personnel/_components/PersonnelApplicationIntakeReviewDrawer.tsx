"use client";

import * as React from "react";
import { PPR_CARD_SECTIONS } from "@/lib/pprCardSections";
import { emptyIntakeDraftPayload, toIntakeFormPayload, type IntakeDraftPayload } from "@/app/intake/_lib/intakeApi.client";
import { buildIntakeReviewSections, type IntakeReviewSectionContent } from "@/app/intake/_lib/intakeReviewContent";

import { formatPersonnelApplicationDateTime } from "../_lib/personnelApplicationLabels";
import {
  acceptIntakeSection,
  getIntakeReviewState,
  mapPersonnelApplicationsApiError,
  reworkIntakeSection,
  skipIntakeSection,
  transferIntakeToPpr,
  type IntakeReviewSection,
  type IntakeReviewState,
} from "../_lib/personnelApplicationsApi.client";
import EducationReconciliationDecisionsPanel from "./EducationReconciliationDecisionsPanel";

type Props = {
  applicationId: number | null;
  open: boolean;
  onClose: () => void;
  onTransferred?: () => void;
};

const MILITARY_FIELDS: ReadonlyArray<[string, string]> = [
  ["rank", "\u0412\u043e\u0438\u043d\u0441\u043a\u043e\u0435 \u0437\u0432\u0430\u043d\u0438\u0435"], ["category", "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u0437\u0430\u043f\u0430\u0441\u0430"], ["composition", "\u0421\u043e\u0441\u0442\u0430\u0432"], ["commissariat", "\u0412\u043e\u0435\u043d\u043a\u043e\u043c\u0430\u0442"], ["specialty_code", "\u0412\u043e\u0438\u043d\u0441\u043a\u043e-\u0443\u0447\u0451\u0442\u043d\u0430\u044f \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0441\u0442\u044c (\u043a\u043e\u0434)"], ["specialty_name", "\u0412\u043e\u0438\u043d\u0441\u043a\u043e-\u0443\u0447\u0451\u0442\u043d\u0430\u044f \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0441\u0442\u044c"], ["fitness_category", "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u0433\u043e\u0434\u043d\u043e\u0441\u0442\u0438"], ["registration_group", "\u0413\u0440\u0443\u043f\u043f\u0430 \u0443\u0447\u0451\u0442\u0430"], ["registration_category", "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u0443\u0447\u0451\u0442\u0430"],
];

function renderMilitaryPayload(payload: Record<string, unknown> | unknown[]): React.ReactNode {
  const values = !Array.isArray(payload) && payload && typeof payload === "object" ? payload : {};
  const rows = MILITARY_FIELDS.filter(([key]) => values[key] != null && String(values[key]).trim() !== "");
  const status = String(values.status ?? "").trim();
  if (rows.length === 0 && (!status || status === "not_provided")) {
    return <p className="text-sm text-zinc-600 dark:text-zinc-300" data-testid="intake-review-military-not-provided">Сведения о воинском учёте не предоставлены</p>;
  }
  return <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2" data-testid="intake-review-military-details">
    {status ? <><dt className="text-zinc-500">Статус</dt><dd>{status}</dd></> : null}
    {rows.map(([key, label]) => <React.Fragment key={key}><dt className="text-zinc-500">{label}</dt><dd>{String(values[key])}</dd></React.Fragment>)}
  </dl>;
}

function renderPayload(payload: Record<string, unknown> | unknown[], sectionCode?: string): React.ReactNode {
  if (sectionCode === "military") return renderMilitaryPayload(payload);
  if (Array.isArray(payload) && payload.length === 0) return <span className="text-zinc-500">Нет записей</span>;
  return null;
}

const REVIEW_TO_CARD: Record<string, string> = {
  contacts: "contacts", personal: "general", education: "education", training: "training",
  employment_biography: "employment_biography", military: "military", relatives: "family", additional: "additional",
};
const REVIEW_ORDER = new Map<string, number>(PPR_CARD_SECTIONS.map((section, index) => [section.id, index]));

function renderReviewFields(fields: { label: string; value: string }[]): React.ReactNode {
  return <dl className="grid gap-2 text-sm sm:grid-cols-2">{fields.map((field, index) =>
    <div key={`${field.label}-${index}`}><dt className="text-zinc-500">{field.label}</dt><dd className="text-zinc-900 dark:text-zinc-100">{field.value}</dd></div>,
  )}</dl>;
}

function renderCardContent(content: IntakeReviewSectionContent): React.ReactNode {
  if (content.empty) return <p className="text-sm text-zinc-500">Нет сведений</p>;
  return <div className="space-y-3">
    {renderReviewFields(content.fields)}
    {content.records.map((record, index) => <div key={index} className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
      <h4 className="mb-2 text-sm font-medium">{record.title}</h4>{renderReviewFields(record.lines)}
    </div>)}
    {content.subsections.map((subsection) => <div key={subsection.testId} className="space-y-2">
      <h4 className="text-sm font-medium">{subsection.title}</h4>
      {subsection.empty ? <p className="text-sm text-zinc-500">Нет сведений</p> : subsection.records.map((record, index) =>
        <div key={index} className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900"><h5 className="mb-2 text-sm font-medium">{record.title}</h5>{renderReviewFields(record.lines)}</div>)}
    </div>)}
  </div>;
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "accepted":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "rework_requested":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
    case "skipped":
      return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
    default:
      return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200";
  }
}

export default function PersonnelApplicationIntakeReviewDrawer({
  applicationId,
  open,
  onClose,
  onTransferred,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [busySection, setBusySection] = React.useState<string | null>(null);
  const [transferring, setTransferring] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [state, setState] = React.useState<IntakeReviewState | null>(null);
  const [reworkSection, setReworkSection] = React.useState<string | null>(null);
  const [reworkComment, setReworkComment] = React.useState("");

  const reload = React.useCallback(async () => {
    if (applicationId == null) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getIntakeReviewState(applicationId);
      setState(data);
    } catch (e) {
      setState(null);
      setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить review"));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  React.useEffect(() => {
    if (!open || applicationId == null) {
      setState(null);
      setError(null);
      setReworkSection(null);
      setReworkComment("");
      return;
    }
    void reload();
  }, [open, applicationId, reload]);

  async function runSectionAction(
    section: IntakeReviewSection,
    action: "accept" | "skip" | "rework",
  ) {
    if (applicationId == null) return;
    setBusySection(section.section_code);
    setError(null);
    try {
      let next: IntakeReviewState;
      if (action === "accept") {
        next = await acceptIntakeSection(applicationId, section.section_code);
      } else if (action === "skip") {
        next = await skipIntakeSection(applicationId, section.section_code);
      } else {
        if (!reworkComment.trim()) {
          setError("Укажите комментарий для доработки.");
          return;
        }
        next = await reworkIntakeSection(applicationId, section.section_code, reworkComment.trim());
        setReworkSection(null);
        setReworkComment("");
      }
      setState(next);
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось выполнить действие"));
    } finally {
      setBusySection(null);
    }
  }

  async function handleTransfer() {
    if (applicationId == null) return;
    setTransferring(true);
    setError(null);
    try {
      await transferIntakeToPpr(applicationId);
      await reload();
      onTransferred?.();
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось перенести данные в PPR"));
    } finally {
      setTransferring(false);
    }
  }

  if (!open) return null;

  const transferDone = state?.transfer?.status === "completed";
  const sourcePayload = state?.draft.payload;
  const formPayload = sourcePayload
    ? toIntakeFormPayload({ ...emptyIntakeDraftPayload(), ...sourcePayload } as IntakeDraftPayload)
    : null;
  const cardContent = formPayload
    ? new Map(buildIntakeReviewSections(formPayload, false).map((content) => [content.stepId, content]))
    : new Map<string, IntakeReviewSectionContent>();
  const sortedSections = [...(state?.sections ?? [])].sort((left, right) =>
    (REVIEW_ORDER.get(REVIEW_TO_CARD[left.section_code]) ?? 99) -
    (REVIEW_ORDER.get(REVIEW_TO_CARD[right.section_code]) ?? 99));

  return (
    <div className="fixed inset-0 z-[70] flex justify-end" data-testid="intake-review-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-4xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold">Проверка анкеты #{applicationId ?? "—"}</h2>
            {state?.transfer?.transferred_at ? (
              <p className="mt-1 text-sm text-zinc-500">
                Перенос выполнен {formatPersonnelApplicationDateTime(state.transfer.transferred_at)}
                {state.transfer.transferred_by_user_id
                  ? ` · user #${state.transfer.transferred_by_user_id}`
                  : ""}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading ? <p className="text-sm text-zinc-500">Загрузка…</p> : null}
          {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

          {state ? (
            <div className="space-y-4">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">Данные отправленной анкеты и решения кадровика по разделам.</p>
              {sortedSections.map((section) => (
                <React.Fragment key={section.section_code}>
                {section.section_code === "additional" && cardContent.get("additional")?.subsections[0] ? (
                  <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" data-testid="intake-review-section-languages">
                    <h3 className="font-medium text-zinc-900 dark:text-zinc-50">{PPR_CARD_SECTIONS.find((item) => item.id === "languages")?.title}</h3>
                    <p className="mb-3 text-xs text-zinc-500">Решение кадровика относится к разделу «Примечание» ниже.</p>
                    {renderCardContent({ ...cardContent.get("additional")!,
                      fields: [], records: [], subsections: cardContent.get("additional")!.subsections.slice(0, 1),
                      empty: cardContent.get("additional")!.subsections[0].empty })}
                  </section>
                ) : null}
                <section
                  className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
                  data-testid={`intake-review-section-${section.section_code}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="font-medium text-zinc-900 dark:text-zinc-50">{PPR_CARD_SECTIONS.find((item) => item.id === REVIEW_TO_CARD[section.section_code])?.title ?? section.section_label}</h3>
                      <span
                        className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(section.status)}`}
                      >
                        {{ accepted: "Принят", skipped: "Пропущен", pending: "Ожидает решения", rework_requested: "На доработке" }[section.status] ?? section.status}
                      </span>
                      {section.rework_comment ? (
                        <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
                          Комментарий: {section.rework_comment}
                        </p>
                      ) : null}
                    </div>
                    {!transferDone ? (
                      <div className="flex flex-wrap gap-2">
                        {!section.is_empty ? (
                          <button
                            type="button"
                            disabled={busySection != null}
                            onClick={() => void runSectionAction(section, "accept")}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                          >
                            Принять
                          </button>
                        ) : null}
                        {section.is_empty ? (
                          <button
                            type="button"
                            disabled={busySection != null}
                            onClick={() => void runSectionAction(section, "skip")}
                            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
                          >
                            Пропустить
                          </button>
                        ) : null}
                        <button
                          type="button"
                          disabled={busySection != null}
                          onClick={() => {
                            setReworkSection(section.section_code);
                            setReworkComment(section.rework_comment || "");
                          }}
                          className="rounded-lg border border-amber-300 px-3 py-1.5 text-sm text-amber-800 dark:border-amber-900 dark:text-amber-300"
                        >
                          Вернуть на доработку
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-3" data-testid={`intake-review-card-content-${section.section_code}`}>
                    {sourcePayload?.personal && cardContent.get(section.section_code)
                      ? renderCardContent(section.section_code === "additional"
                        ? { ...cardContent.get("additional")!,
                            subsections: cardContent.get("additional")!.subsections.slice(1),
                            empty: cardContent.get("additional")!.subsections.slice(1).every((part) => part.empty) }
                        : cardContent.get(section.section_code)!)
                      : renderPayload(section.payload as Record<string, unknown> | unknown[], section.section_code)}
                  </div>
                  <details className="mt-3 text-sm"><summary role="button" className="inline-flex cursor-pointer rounded-lg border border-zinc-300 px-3 py-1.5 text-blue-700 dark:border-zinc-700 dark:text-blue-300">Показать JSON</summary>
                    <pre className="mt-2 overflow-x-auto rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">{JSON.stringify(section.payload, null, 2)}</pre>
                  </details>
                  {section.section_code === "education" && applicationId != null ? (
                    <EducationReconciliationDecisionsPanel
                      applicationId={applicationId}
                      educationPayload={section.payload as Record<string, unknown> | unknown[]}
                      onReviewDataChanged={reload}
                    />
                  ) : null}
                  {reworkSection === section.section_code ? (
                    <div className="mt-3 space-y-2">
                      <textarea
                        value={reworkComment}
                        onChange={(e) => setReworkComment(e.target.value)}
                        className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                        rows={3}
                        placeholder="Комментарий для претендента / HR"
                      />
                      <button
                        type="button"
                        disabled={busySection != null}
                        onClick={() => void runSectionAction(section, "rework")}
                        className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                      >
                        Отправить на доработку
                      </button>
                    </div>
                  ) : null}
                </section>
                </React.Fragment>
              ))}

              {state.transfer_blocked_reason && !state.can_transfer ? (
                <p className="text-sm text-zinc-500">{state.transfer_blocked_reason}</p>
              ) : null}

              {state.can_transfer && !transferDone ? (
                <button
                  type="button"
                  disabled={transferring}
                  onClick={() => void handleTransfer()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  data-testid="intake-transfer-button"
                >
                  {transferring ? "Перенос…" : "Перенести в PPR"}
                </button>
              ) : null}

              {state.transfer ? (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
                  <div className="font-medium">Журнал переноса</div>
                  <div className="mt-1">Статус: {state.transfer.status}</div>
                  <div>Результат: {state.transfer.result || "—"}</div>
                  <div>Разделы: {state.transfer.sections_transferred.join(", ") || "—"}</div>
                  {state.transfer.error_message ? (
                    <div className="mt-1 text-red-600">{state.transfer.error_message}</div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
