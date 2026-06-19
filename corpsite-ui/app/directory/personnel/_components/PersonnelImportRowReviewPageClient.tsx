"use client";

import * as React from "react";
import Link from "next/link";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import ImportFieldDiffPanel from "./ImportFieldDiffPanel";
import {
  getRowReviewDetail,
  mapImportApiError,
  runRowAiExtraction,
  type RowReviewDetail,
} from "../_lib/importApi.client";
import { calcRecordValidityNote } from "../_lib/importProfileEditor";

const EDUCATION_SECTION_LABELS: Record<string, string> = {
  basic: "Базовое образование",
  internship: "Интернатура",
  residency: "Резидентура",
  masters: "Магистратура",
  phd: "PhD / учёная степень",
};

const SEX_LABELS: Record<string, string> = {
  M: "Мужской",
  F: "Женский",
};

function SectionTable({
  title,
  headers,
  rows,
}: {
  title: string;
  headers: string[];
  rows: string[][];
}) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">{title}</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[11px] uppercase text-zinc-500">
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-2 py-1">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((cells, idx) => (
              <tr key={idx} className="border-t border-zinc-100 dark:border-zinc-800">
                {cells.map((cell, ci) => (
                  <td key={ci} className="px-2 py-2">
                    {cell || "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AiExtractionSection({
  detail,
  onRefresh,
}: {
  detail: RowReviewDetail;
  onRefresh: () => void;
}) {
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const draft = detail.ai_extraction;

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      await runRowAiExtraction(detail.batch_id, detail.row_id);
      onRefresh();
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setRunning(false);
    }
  }

  const extraction = draft?.extraction;
  const hasItems =
    extraction &&
    (extraction.education.length > 0 ||
      extraction.training.length > 0 ||
      extraction.certificates.length > 0 ||
      extraction.categories.length > 0 ||
      extraction.awards.length > 0 ||
      extraction.degrees.length > 0);

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900 dark:bg-amber-950/20">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
            AI-извлечение
          </h2>
          <p className="text-xs text-amber-700 dark:text-amber-400">
            AI-предложение. Требуется проверка.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          className="rounded border border-amber-400 px-3 py-1.5 text-sm text-amber-900 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900/40"
        >
          {running ? "Извлечение…" : draft ? "Перезапустить AI" : "Запустить AI-извлечение"}
        </button>
      </div>
      {error ? <div className="mb-2 text-sm text-red-600">{error}</div> : null}
      {!draft ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          AI-черновик ещё не создан. Нажмите «Запустить AI-извлечение» для нормализации сложных
          текстовых полей.
        </p>
      ) : null}
      {draft?.extraction.warnings?.length ? (
        <ul className="mb-3 list-disc pl-5 text-xs text-amber-800 dark:text-amber-300">
          {draft.extraction.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      ) : null}
      {hasItems ? (
        <div className="space-y-3 text-sm">
          {extraction!.education.length > 0 ? (
            <div>
              <h3 className="font-medium">Образование ({extraction!.education.length})</h3>
              <ul className="mt-1 space-y-1 text-xs text-zinc-700 dark:text-zinc-300">
                {extraction!.education.map((item, i) => (
                  <li key={i}>
                    {String(item.institution || item.specialty || "—")} · conf.{" "}
                    {Math.round(Number(item.confidence ?? 0) * 100)}%
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {extraction!.training.length > 0 ? (
            <div>
              <h3 className="font-medium">Повышение квалификации ({extraction!.training.length})</h3>
            </div>
          ) : null}
          {extraction!.categories.length > 0 ? (
            <div>
              <h3 className="font-medium">Категории ({extraction!.categories.length})</h3>
            </div>
          ) : null}
          {extraction!.certificates.length > 0 ? (
            <div>
              <h3 className="font-medium">Сертификаты ({extraction!.certificates.length})</h3>
            </div>
          ) : null}
          {extraction!.awards.length > 0 ? (
            <div>
              <h3 className="font-medium">Награды ({extraction!.awards.length})</h3>
            </div>
          ) : null}
          {extraction!.degrees.length > 0 ? (
            <div>
              <h3 className="font-medium">Учёные степени ({extraction!.degrees.length})</h3>
            </div>
          ) : null}
        </div>
      ) : draft && !draft.extraction.warnings?.length ? (
        <p className="text-sm text-zinc-500">AI не нашёл структурированных данных в текстовых полях.</p>
      ) : null}
    </section>
  );
}

export default function PersonnelImportRowReviewPageClient({
  batchId,
  rowId,
}: {
  batchId: number;
  rowId: number;
}) {
  const [detail, setDetail] = React.useState<RowReviewDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const loadDetail = React.useCallback(() => {
    setLoading(true);
    getRowReviewDetail(batchId, rowId)
      .then((data) => {
        setDetail(data);
        setError(null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [batchId, rowId]);

  React.useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const profile = detail?.profile;

  return (
    <div className="px-4 py-3">
      <div className="mb-4">
        <Link
          href={`/directory/personnel/import/${batchId}/review`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← Назад к review
        </Link>
      </div>

      {error ? <div className="mb-4 text-sm text-red-600">{error}</div> : null}
      {loading || !detail ? (
        <div className="py-12 text-center text-zinc-500">Загрузка карточки…</div>
      ) : (
        <div className="space-y-4">
          <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold">{detail.full_name || "—"}</h1>
              <ImportDiffStatusBadge status={detail.diff_status} />
            </div>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <span className="text-zinc-500">ИИН:</span> {detail.iin_masked || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Дата рождения:</span> {detail.birth_date || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Пол:</span>{" "}
                {detail.sex ? SEX_LABELS[detail.sex] || detail.sex : "—"}
              </div>
              <div>
                <span className="text-zinc-500">Должность:</span> {detail.position_raw || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Отделение (канон.):</span>{" "}
                {detail.department_recoding?.org_unit_name || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Отделение (исходное):</span>{" "}
                {detail.department_source || detail.department || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Стаж:</span> {detail.experience_raw || "—"}
              </div>
              <div>
                <span className="text-zinc-500">Ставка:</span>{" "}
                {detail.employment_rate != null ? String(detail.employment_rate) : "—"}
              </div>
            </div>
            <div className="mt-2 text-xs text-zinc-500">
              row #{detail.row_id} · {detail.source_sheet}:{detail.source_row_number}
              {detail.is_part_time ? " · совмещ" : ""}
              {detail.employee_id ? ` · employee_id=${detail.employee_id}` : ""}
            </div>
          </section>

          <ImportFieldDiffPanel fieldDiffs={detail.field_diffs} recordKind="roster" />

          {profile
            ? Object.entries(profile.education).map(([key, records]) => (
                <SectionTable
                  key={key}
                  title={EDUCATION_SECTION_LABELS[key] || key}
                  headers={["Учебное заведение", "Специальность", "Дата", "Уверенность"]}
                  rows={records.map((r) => [
                    r.institution,
                    r.specialty,
                    r.completed_at,
                    r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "",
                  ])}
                />
              ))
            : null}

          <SectionTable
            title="Повышение квалификации"
            headers={["Курс", "Организация", "Часы", "Дата"]}
            rows={
              profile?.training_records.map((t) => [
                t.title,
                t.organization,
                t.hours != null ? String(t.hours) : "",
                t.completed_at,
              ]) ??
              detail.training.map((t) => [t.title, "", t.hours != null ? String(t.hours) : "", t.year])
            }
          />

          <SectionTable
            title="Квалификационные категории"
            headers={["Категория", "Специальность", "Дата", "Примечание"]}
            rows={
              profile?.category_records.map((q) => [
                q.category,
                q.specialty,
                q.issued_at,
                calcRecordValidityNote(q.issued_at) ?? "",
              ]) ??
              detail.qualification_categories.map((q) => [
                q.category,
                q.specialty,
                q.date,
                calcRecordValidityNote(q.date) ?? "",
              ])
            }
          />

          <SectionTable
            title="Сертификаты"
            headers={["Специальность", "Дата выдачи", "Дата окончания", "Примечание"]}
            rows={
              profile?.certificate_records.map((c) => [
                c.specialty,
                c.issued_at,
                c.valid_until,
                calcRecordValidityNote(c.issued_at) ?? "",
              ]) ??
              detail.certificates.map((c) => [
                c.topic,
                c.date,
                c.valid_until || "",
                calcRecordValidityNote(c.date) ?? "",
              ])
            }
          />

          <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Учёные степени
            </h2>
            <ul className="text-sm">
              {detail.degrees.candidate_medical_sciences ? <li>Кандидат медицинских наук</li> : null}
              {detail.degrees.doctor_medical_sciences ? <li>Доктор медицинских наук</li> : null}
              {!detail.degrees.candidate_medical_sciences && !detail.degrees.doctor_medical_sciences ? (
                <li className="text-zinc-500">—</li>
              ) : null}
            </ul>
          </section>

          <SectionTable
            title="Награды"
            headers={["Награда", "Дата"]}
            rows={
              profile?.award_records.map((a) => [a.title, a.date]) ??
              detail.awards.map((a) => [a.title, a.date])
            }
          />

          {detail.notes.length > 0 ? (
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                Примечания
              </h2>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {detail.notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <AiExtractionSection detail={detail} onRefresh={loadDetail} />
        </div>
      )}
    </div>
  );
}
