"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { removeTrainingEvidence, trainingApi, trainingEvidenceUrl, uploadTrainingEvidence, type TrainingDetail } from "@/lib/trainingApi";
import TrainingNavigation from "../../_components/TrainingNavigation";
import TrainingReviewReceipt from "../../_components/TrainingReviewReceipt";
import { trainingDate, trainingLessonTitle } from "@/lib/trainingViewModel";

type HireRecord = {
  application_number: number; full_name: string; org_unit: string; position: string;
  rate: string; start_date: string; order_number: number; task_number: number;
  task_status: string; order_status: string; order_visa_valid: boolean;
  visa: null | { decision: string; is_current: boolean; decided_by_name: string; decided_at: string };
  technical_message?: string;
};

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Не удалось выполнить действие.";
}

function approved(record: HireRecord) {
  return record.visa?.decision === "approved" && record.visa.is_current;
}

function decisionTime(record: HireRecord) {
  return record.visa ? new Date(record.visa.decided_at).toLocaleString("ru-RU", { timeZone: "Asia/Qyzylorda" }) : "—";
}

function makeResultImage(record: HireRecord): Promise<File> {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement("canvas");
    canvas.width = 1200;
    canvas.height = 900;
    const ctx = canvas.getContext("2d");
    if (!ctx) { reject(new Error("Браузер не смог подготовить изображение. Выберите файл вручную.")); return; }
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#172033";
    ctx.font = "bold 38px Arial";
    ctx.fillText("Результат согласования заявления", 48, 76);
    ctx.font = "28px Arial";
    const lines = [
      `Заявление о приёме № ${record.application_number}`,
      `Кандидат: ${record.full_name}`,
      `Отделение: ${record.org_unit}`,
      `Должность: ${record.position}`,
      `Ставка: ${record.rate} · дата начала: ${record.start_date}`,
      `Решение: ${approved(record) ? "Согласен, сохранено" : "Не сохранено"}`,
      `Согласовал: ${record.visa?.decided_by_name ?? "—"}`,
      `Время решения: ${decisionTime(record)}`,
      `Статус заявления: ${approved(record) ? "Согласовано" : "Ожидает согласования"}`,
      `Задача № ${record.task_number}: ${record.task_status === "DONE" ? "Завершена" : "В работе"}`,
      `Виза в связанном приказе: ${record.order_visa_valid ? "Положительная" : "Ожидается"}`,
      `Внутренний ID черновика приказа: ${record.order_number}`,
      `Статус приказа: ${record.order_status === "DRAFT" ? "Черновик" : record.order_status}`,
    ];
    let y = 145;
    for (const line of lines) {
      const words = line.split(" ");
      let current = "";
      for (const word of words) {
        const candidate = current ? `${current} ${word}` : word;
        if (ctx.measureText(candidate).width > 1090 && current) {
          ctx.fillText(current, 48, y); y += 47; current = word;
        } else current = candidate;
      }
      ctx.fillText(current, 48, y); y += 55;
    }
    if (y > canvas.height - 20) { reject(new Error("Данные не помещаются на снимке. Выберите файл вручную.")); return; }
    canvas.toBlob((blob) => blob
      ? resolve(new File([blob], `result-application-${record.application_number}.png`, { type: "image/png" }))
      : reject(new Error("Снимок не сформирован. Выберите файл вручную.")), "image/png");
  });
}

export default function HireLesson({ attemptId, detail, onRefresh }: {
  attemptId: number; detail: TrainingDetail; onRefresh: () => Promise<void>;
}) {
  const [record, setRecord] = useState<HireRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<File | null>(null);
  const [pendingUrl, setPendingUrl] = useState("");
  const [savedUrl, setSavedUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const evidence = detail.evidence.find((item) => item.step_key === "result");
  const evidenceId = evidence?.evidence_id;
  const complete = detail.attempt.status === "completed";
  const submitted = detail.attempt.status === "under_review";
  const loadRecord = useCallback(async () => setRecord(await trainingApi.hireRecord(attemptId) as HireRecord), [attemptId]);
  useEffect(() => { void loadRecord().catch((error) => setMessage(errorText(error))); }, [loadRecord]);
  useEffect(() => {
    if (!evidenceId) { setSavedUrl(""); return; }
    let current = "";
    let mounted = true;
    void trainingEvidenceUrl(evidenceId).then((url) => {
      current = url;
      if (mounted) setSavedUrl(url);
      else URL.revokeObjectURL(url);
    })
      .catch((error) => setMessage(errorText(error)));
    return () => { mounted = false; if (current) URL.revokeObjectURL(current); };
  }, [evidenceId]);
  useEffect(() => {
    if (!pending) { setPendingUrl(""); return; }
    const url = URL.createObjectURL(pending);
    setPendingUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [pending]);

  async function consent() {
    setBusy(true); setMessage("");
    try { setRecord(await trainingApi.hireConsent(attemptId) as HireRecord); await onRefresh(); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }
  function choose(file?: File) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) { setMessage("Выберите PNG, JPEG или WebP."); return; }
    if (file.size > 5 * 1024 * 1024) { setMessage("Размер снимка не должен превышать 5 МБ."); return; }
    setPending(file); setMessage("");
  }
  async function generate() {
    if (!record || !approved(record)) return;
    setBusy(true); setMessage("");
    try {
      const current = await trainingApi.hireRecord(attemptId) as HireRecord;
      setRecord(current);
      if (!approved(current)) throw new Error("Согласие больше не действует. Проверьте заявление перед снимком.");
      choose(await makeResultImage(current));
    }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!pending) return;
    setBusy(true); setMessage("");
    try { await uploadTrainingEvidence(attemptId, "result", pending); setPending(null); await onRefresh(); setMessage("Подтверждение сохранено."); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!evidence) return;
    setBusy(true); setMessage("");
    try { await removeTrainingEvidence(evidence.evidence_id); await onRefresh(); setMessage("Подтверждение удалено."); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true); setMessage("");
    try { const response = await trainingApi.check(attemptId); await onRefresh(); if (response.status !== "under_review") setMessage(response.message); }
    catch (error) { setMessage(errorText(error)); }
    finally { setBusy(false); }
  }
  const visa = record?.visa;
  const isApproved = record ? approved(record) : false;
  const lastReview = detail.reviews.at(-1);
  const gradedReview = detail.reviews.filter((review) => review.score !== null).at(-1);
  return <div className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
    <TrainingNavigation active="lessons" />
    <header><p className="text-sm text-zinc-500">Курс: {detail.attempt.course_title}</p>
      <h1 className="text-2xl font-semibold">{trainingLessonTitle(detail.attempt.lesson_number, detail.attempt.lesson_title)}</h1>
      <p className="text-sm text-zinc-500">Попытка {detail.attempt.attempt_number} · {detail.attempt.duration_minutes} минут · версия материала {detail.attempt.course_version}</p></header>
    {complete && gradedReview && <TrainingReviewReceipt title="Результат проверки" data={{
      courseTitle: detail.attempt.course_title, lessonNumber: detail.attempt.lesson_number,
      lessonTitle: detail.attempt.lesson_title, attemptNumber: detail.attempt.attempt_number,
      applicationNumber: String(detail.attempt.fixture.application_number ?? ""),
      score: gradedReview.score!, reviewedAt: gradedReview.created_at,
      reviewerName: gradedReview.reviewer_name, explanation: gradedReview.explanation,
    }} />}
    <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <section className="min-w-0 rounded-xl border bg-white p-5 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold">Инструкция и образец</h2>
        <ol className="mt-3 list-decimal space-y-3 pl-5 text-sm">
          <li>Прочитайте условия индивидуального заявления справа.</li>
          <li>Сверьте кандидата, отделение, должность, ставку и дату начала.</li>
          <li>Нажмите «Согласен» и проверьте сохранённое решение и статусы.</li>
          <li>Сделайте снимок результата или загрузите один читаемый снимок.</li>
          <li>Проверьте предпросмотр и отправьте результат эксперту по внутреннему обучению.</li>
        </ol>
        <div className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-950 dark:bg-zinc-800 dark:text-zinc-100">
          <strong>Образец результата:</strong> согласие сохранено; задача завершена; в связанном приказе положительная виза; приказ остаётся черновиком.
          Значения справа относятся только к вашей попытке.
        </div>
      </section>
      <section className="min-w-0 space-y-4 rounded-xl border bg-white p-5 dark:bg-zinc-900" aria-label="Текущая учебная запись">
        <h2 className="text-lg font-semibold">Индивидуальное учебное заявление</h2>
        {!record ? <p>Загрузка заявления…</p> : <div id="hire-result-record" className="space-y-3 break-words text-sm">
          <p className="text-xl font-semibold">Заявление о приёме № {record.application_number}</p>
          <p><strong>Кандидат:</strong> {record.full_name}<br /><strong>Отделение:</strong> {record.org_unit}<br />
            <strong>Должность:</strong> {record.position}<br /><strong>Ставка:</strong> {record.rate}<br /><strong>Дата начала:</strong> {record.start_date}</p>
          <p><strong>Задача № {record.task_number}</strong> · внутренний ID черновика приказа {record.order_number}</p>
          {isApproved ? <div className="rounded-lg border border-green-300 bg-green-50 p-3 text-green-950">
            <strong>Согласен · решение сохранено</strong><br />Согласовал: {visa?.decided_by_name} · {decisionTime(record)}
          </div> : <button type="button" disabled={busy || complete} onClick={() => void consent()}
            className="rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-50">Согласен</button>}
          {isApproved && detail.attempt.status === "technical_pause" && <button type="button" disabled={busy} onClick={() => void consent()} className="rounded-lg border px-3 py-2">Повторить проверку визы</button>}
          <div className="rounded-lg border p-3"><strong>Итоговые статусы</strong>
            <p>Заявление: {isApproved ? "Согласовано" : "Ожидает согласования"}</p>
            <p>Задача: {record.task_status === "DONE" ? "Завершена" : "В работе"}</p>
            <p>Виза в связанном приказе: {record.order_visa_valid ? "Положительная" : "Ожидается"}</p>
            <p>Приказ: {record.order_status === "DRAFT" ? "Черновик" : record.order_status} · регистрационный номер {record.order_status === "DRAFT" ? "не присвоен" : record.order_number}</p>
          </div>
          {record.technical_message && <p role="alert" className="rounded-lg bg-amber-50 p-3">{record.technical_message}</p>}
        </div>}
      </section>
    </div>
    <section className="min-w-0 rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <h2 className="text-lg font-semibold">Результат согласования заявления</h2>
      <p className="mt-1 text-sm">Одно обязательное подтверждение. Один снимок может показывать несколько выполненных действий.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" disabled={!isApproved || busy || complete} onClick={() => void generate()} className="rounded-lg bg-blue-700 px-3 py-2 text-sm text-white disabled:opacity-50">Сделать снимок результата</button>
        <button type="button" disabled={busy || complete} onClick={() => inputRef.current?.click()} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{evidence ? "Заменить файлом" : "Выбрать файл"}</button>
        <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" aria-label="Выбрать снимок" onChange={(event) => { choose(event.target.files?.[0]); event.currentTarget.value = ""; }} />
      </div>
      {!complete && <div tabIndex={0} className="mt-3 rounded-lg border-2 border-dashed p-4 text-sm"
        onPaste={(event) => { const file = Array.from(event.clipboardData.files).find((item) => item.type.startsWith("image/")); if (file) { event.preventDefault(); choose(file); } }}
        onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}>
        Можно вставить изображение Ctrl+V или перетащить файл сюда.
      </div>}
      {pending && <div className="mt-4 space-y-2"><p className="font-medium">Предпросмотр перед прикреплением</p>
        {pendingUrl && <img src={pendingUrl} alt="Предпросмотр подтверждения" className="max-h-[32rem] max-w-full rounded-lg border object-contain" />}
        <div className="flex gap-2"><button type="button" disabled={busy} onClick={() => void save()} className="rounded-lg bg-blue-700 px-3 py-2 text-white disabled:opacity-50">Прикрепить снимок</button>
          <button type="button" onClick={() => setPending(null)} className="rounded-lg border px-3 py-2">Отмена</button></div>
      </div>}
      {evidence && <div className="mt-4 space-y-2"><p className="font-medium">Прикреплено: 1 из 1</p>
        {savedUrl && <img src={savedUrl} alt="Сохранённое подтверждение" className="max-h-[32rem] max-w-full rounded-lg border object-contain" />}
        {!complete && <button type="button" disabled={busy} onClick={() => void remove()} className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 disabled:opacity-50">Удалить</button>}
      </div>}
      {!evidence && <p className="mt-3 text-sm">Прикреплено: 0 из 1</p>}
      {!submitted && !complete && <button type="button" disabled={busy || !evidence || !!pending || !isApproved} onClick={() => void submit()}
        className="mt-4 rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-50">Отправить на проверку</button>}
    </section>
    <section className="rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <h2 className="text-lg font-semibold">Результат проверки</h2>
      <p className="mt-2">Состояние: {submitted ? "На проверке" : complete ? (detail.attempt.outcome === "passed" ? "Зачтено" : "Не зачтено") : "В работе"}</p>
      <p>Оценка: {detail.attempt.score ?? "—"} · Проверено: {complete ? trainingDate(detail.attempt.last_checked_at) : "—"}</p>
      {submitted && <p className="mt-2 text-sm">Результат отправлен эксперту по внутреннему обучению. Оценка появится после проверки.</p>}
      {complete && Boolean(lastReview?.explanation) && <p className="mt-2 text-sm">Пояснение: {String(lastReview?.explanation)}</p>}
      <details className="mt-3 text-sm"><summary className="cursor-pointer">История проверок и технические подробности</summary>
        {detail.reviews.length === 0 ? <p className="mt-2">Проверок ещё нет.</p> : <ul className="mt-2 list-disc pl-5">{detail.reviews.map((review, index) => <li key={String(review.review_id ?? index)}>
          {review.score == null ? "Ожидает оценки" : `Оценка ${review.score}`} · {review.created_at ? trainingDate(String(review.created_at)) : "—"} · {String(review.explanation ?? "")}
        </li>)}</ul>}
      </details>
    </section>
    {message && <p role="status" className="rounded-lg border p-3 text-sm">{message}</p>}
  </div>;
}
