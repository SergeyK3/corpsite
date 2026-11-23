"use client";

import Link from "next/link";
import { trainingDateTime, trainingLessonTitle } from "@/lib/trainingViewModel";

export type TrainingReviewReceiptData = {
  courseTitle: string; lessonNumber: number; lessonTitle: string;
  attemptNumber: number; applicationNumber: string | null;
  score: number; reviewedAt: string; reviewerName: string | null;
  explanation: string; attemptId?: number;
};

export default function TrainingReviewReceipt({ title, data }: {
  title: string; data: TrainingReviewReceiptData;
}) {
  return <section className="min-w-0 rounded-xl border border-blue-300 bg-blue-50 p-4 text-sm text-blue-950 dark:border-blue-800 dark:bg-blue-950/35 dark:text-blue-100">
    <h2 className="text-lg font-semibold">{title}</h2>
    <p className="mt-2">Курс: {data.courseTitle}</p>
    <p className="font-medium">{trainingLessonTitle(data.lessonNumber, data.lessonTitle)}</p>
    <p>Попытка {data.attemptNumber} · заявление №{data.applicationNumber ?? "—"}</p>
    <p className="mt-2"><strong>Работу проверил: Эксперт по внутреннему обучению — {data.reviewerName?.trim() || "Проверяющий не указан"}</strong></p>
    <p>Оценка: {data.score} · Дата и время проверки: {trainingDateTime(data.reviewedAt)}</p>
    <p className="mt-1">Пояснение эксперта: {data.explanation}</p>
    {data.attemptId && <Link href={`/training/attempts/${data.attemptId}`} className="mt-2 inline-block text-blue-700 underline dark:text-blue-300">Посмотреть результат</Link>}
  </section>;
}
