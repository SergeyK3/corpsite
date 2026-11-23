"use client";

import Link from "next/link";
import TrainingNavigation from "../../_components/TrainingNavigation";
import TrainingReviewReceipt from "../../_components/TrainingReviewReceipt";
import { trainingLessonTitle } from "@/lib/trainingViewModel";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  removeTrainingEvidence, trainingApi, trainingEvidenceUrl, uploadTrainingEvidence,
  type TrainingDetail,
} from "@/lib/trainingApi";
import HireLesson from "./HireLesson";

function errorText(error: unknown): string {
  return typeof error === "object" && error !== null && "message" in error
    ? String(error.message) : "Не удалось выполнить действие.";
}

function EvidenceImage({ id, alt }: { id: number; alt: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let mounted = true;
    let objectUrl = "";
    trainingEvidenceUrl(id).then((value) => {
      objectUrl = value;
      if (mounted) setUrl(value);
      else URL.revokeObjectURL(value);
    });
    return () => { mounted = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id]);
  return url ? <a href={url} target="_blank" rel="noreferrer" aria-label="Увеличить свой скриншот">
    <img src={url} alt={alt} className="max-h-80 w-full rounded-lg object-contain" />
  </a> : <p>Загрузка сохранённого снимка…</p>;
}

export default function TrainingAttemptPage() {
  const params = useParams<{ id: string }>();
  const attemptId = Number(params.id);
  const inputRef = useRef<HTMLInputElement>(null);
  const [detail, setDetail] = useState<TrainingDetail | null>(null);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    if (!Number.isInteger(attemptId) || attemptId < 1) return;
    setDetail(await trainingApi.detail(attemptId));
  }, [attemptId]);
  useEffect(() => { refresh().catch((error) => setMessage(errorText(error))); }, [refresh]);

  const steps = detail?.attempt.steps ?? [];
  const step = steps[index];
  const evidence = detail?.evidence.find((entry) => entry.step_key === step?.key);
  const required = steps.filter((entry) => entry.actor === "participant").length;

  async function saveFile(file: File | undefined) {
    if (!file || !step || step.actor !== "participant") return;
    setBusy(true); setMessage("");
    try {
      await uploadTrainingEvidence(attemptId, step.key, file);
      await refresh();
      setMessage("Снимок сохранён для текущего шага.");
    } catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function remove(id: number) {
    setBusy(true); setMessage("");
    try { await removeTrainingEvidence(id); await refresh(); setMessage("Снимок удалён из текущего подтверждения."); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }

  async function check() {
    setBusy(true); setMessage("");
    try {
      const response = await trainingApi.check(attemptId);
      await refresh();
      setMessage(response.message + (response.missing_steps?.length ? ` Не заполнены: ${response.missing_steps.join(", ")}.` : ""));
    } catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }

  if (!detail) return <div className="mx-auto max-w-6xl p-6">{message || "Загрузка занятия…"}</div>;
  if (detail.attempt.lesson_code === "skill_2" && detail.attempt.course_version === 3) {
    return <HireLesson attemptId={attemptId} detail={detail} onRefresh={refresh} />;
  }
  const attempt = detail.attempt;
  const fixture = attempt.fixture;
  const isHire = attempt.lesson_code === "skill_2" && attempt.course_version === 2;
  const sample = attempt.lesson_code === "skill_8" ? "/training/skill-8-sample.png" : null;
  const gradedReview = detail.reviews.filter((review) => review.score !== null).at(-1);

  return <div className="mx-auto max-w-6xl space-y-5 p-4 md:p-6">
    <TrainingNavigation active="lessons" />
    <header>
      <div className="text-sm text-zinc-500">{isHire ? "Индивидуальное учебное задание" : String(fixture.position ?? "Должность не указана")} · версия курса {attempt.course_version}</div>
      <p className="text-sm text-zinc-500">Курс: {attempt.course_title}</p>
      <h1 className="text-2xl font-semibold">{trainingLessonTitle(attempt.lesson_number, attempt.lesson_title)}</h1>
      <p className="text-sm text-zinc-600">Попытка {attempt.attempt_number}{isHire ? "" : ` · ${String(fixture.full_name ?? "")}`} · {fixture.rate ? `${fixture.rate} ставки` : ""} · {fixture.start_date ? `с ${fixture.start_date}` : ""}</p>
      {Boolean(fixture.application_number || fixture.order_number) && <p className="text-sm">Заявление № {String(fixture.application_number ?? "—")} · Внутренний ID черновика приказа {String(fixture.order_number ?? "—")}</p>}
    </header>
    {isHire && attempt.status === "completed" && gradedReview && <TrainingReviewReceipt title="Результат проверки" data={{
      courseTitle: attempt.course_title, lessonNumber: attempt.lesson_number, lessonTitle: attempt.lesson_title,
      attemptNumber: attempt.attempt_number, applicationNumber: String(fixture.application_number ?? ""),
      score: gradedReview.score!, reviewedAt: gradedReview.created_at,
      reviewerName: gradedReview.reviewer_name, explanation: gradedReview.explanation,
    }} />}
    <section className="rounded-xl border p-4 text-sm">
      <h2 className="font-semibold">Исходные данные вашего задания</h2>
      <p className="mt-1">{isHire ? "Кандидат: " : ""}{String(fixture.full_name ?? "—")} · {isHire ? `${String(fixture.org_unit ?? "—")} · ` : ""}{String(fixture.position ?? "—")} · ставка {String(fixture.rate ?? "—")} · начало работы {String(fixture.start_date ?? "—")}</p>
      {isHire && <p className="mt-2">Задача № {String(fixture.task_number ?? "—")} · <Link href={`/training/attempts/${attemptId}/record`} className="font-medium text-blue-700 underline">Открыть учебную запись</Link></p>}
      {attempt.expected_result && <p className="mt-2"><strong>Ожидаемый результат:</strong> {attempt.expected_result}</p>}
      {attempt.source_data && <details className="mt-2"><summary className="cursor-pointer text-blue-700">Пример исходных данных из руководства</summary><p className="mt-1 text-zinc-500">{attempt.source_data}</p></details>}
    </section>
    {step && <>
      <section className="rounded-xl border bg-zinc-50 p-4 dark:bg-zinc-900">
        <div className="font-semibold">{isHire && step.evidence_label ? step.evidence_label : `Шаг ${index + 1} из ${steps.length}`} {step.actor === "system" ? "· системный партнёр" : ""}</div>
        <p className="mt-2">{step.instruction}</p>
      </section>
      <div className="grid gap-4 md:grid-cols-2">
        {!isHire && <section className="min-w-0 rounded-xl border p-4">
          <h2 className="text-lg font-semibold">Образец в руководстве</h2>
          {sample ? <a href={sample} target="_blank" rel="noreferrer" className="mt-3 block" aria-label="Увеличить образец">
            <img src={sample} alt="Пример должности в заголовке кабинета" className="max-h-80 max-w-full rounded-lg border object-contain" />
          </a> : <p className="mt-3 text-sm text-zinc-500">Для этого шага нет изображения в руководстве.</p>}
          <p className="mt-2 text-xs text-zinc-500">Образец поясняет экран. В вашем задании используйте собственные данные.</p>
        </section>}
        <section className="min-w-0 rounded-xl border p-4">
          <h2 className="text-lg font-semibold">{isHire && step.evidence_label ? step.evidence_label : "Ваш скриншот"}</h2>
          {step.actor === "system" ? <p className="mt-3 text-sm">Этот шаг выполняет система. Подтверждение пользователя не требуется.</p> : <>
            <div className="mt-3 rounded-xl border-2 border-dashed border-blue-300 bg-blue-50 p-4 text-center dark:bg-zinc-900"
              tabIndex={0}
              onPaste={(event) => {
                const file = Array.from(event.clipboardData.files).find((item) => item.type.startsWith("image/"));
                if (file) { event.preventDefault(); void saveFile(file); }
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); void saveFile(event.dataTransfer.files[0]); }}>
              {evidence ? <EvidenceImage id={evidence.evidence_id} alt={`Ваш скриншот: шаг ${index + 1}`} />
                : <p className="py-8 font-medium">Вставьте свой скриншот<br /><span className="text-sm font-normal">Ctrl+V, перетащите или выберите файл</span></p>}
              <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only"
                onChange={(event) => void saveFile(event.target.files?.[0])} aria-label="Выбрать скриншот" />
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="rounded-lg border bg-white px-3 py-2 text-sm text-zinc-900 disabled:opacity-50">
                  {evidence ? "Заменить снимок" : "Выбрать файл"}
                </button>
                {evidence && <button type="button" disabled={busy} onClick={() => void remove(evidence.evidence_id)} className="rounded-lg border border-red-300 bg-white px-3 py-2 text-sm text-red-700 disabled:opacity-50">Удалить</button>}
              </div>
            </div>
            <p className="mt-2 text-xs text-zinc-500">PNG, JPEG или WebP, до 5 МБ. Снимок сохраняется сразу и остаётся после обновления страницы.</p>
          </>}
        </section>
      </div>
    </>}
    {message && <p role="status" className="rounded-lg border p-3 text-sm">{message}</p>}
    <div className="flex flex-wrap items-center gap-2 rounded-xl border p-4">
      <button type="button" disabled={index === 0} onClick={() => setIndex((value) => value - 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Предыдущий</button>
      <button type="button" disabled={index >= steps.length - 1} onClick={() => setIndex((value) => value + 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">Следующий</button>
      <span className="text-sm text-zinc-500">Подтверждения: {detail.evidence.length} из {required}</span>
      <button type="button" disabled={busy} onClick={() => void check()} className="ml-auto rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-50">{isHire ? "Отправить на проверку" : "Получить оценку"}</button>
    </div>
    <p className="text-sm">Состояние: {attempt.status === "under_review" ? "На проверке" : attempt.status === "technical_pause" ? "Техническая пауза" : attempt.status === "completed" ? (attempt.outcome === "passed" ? "Пройдено без замечаний" : "Не выполнено") : "В работе"} · Оценка: {attempt.score ?? "—"}</p>
    {isHire && <section className="rounded-xl border p-4 text-sm">
      <h2 className="font-semibold">История проверки</h2>
      {detail.reviews.length === 0 ? <p className="mt-1">Проверок ещё нет.</p> : <ul className="mt-2 space-y-2">{detail.reviews.map((review, i) => <li key={String(review.review_id ?? i)}>
        {review.score == null ? "На проверке" : `Оценка ${review.score}`} · {String(review.explanation ?? "")}
      </li>)}</ul>}
    </section>}
    <Link href="/training/results" className="text-sm text-blue-700 underline">Мои результаты</Link>
  </div>;
}
