import type { TrainingSummaryItem } from "./trainingApi";

export function trainingLessonTitle(number: number, title: string): string {
  return `Занятие №${number}. ${title}`;
}

export function trainingStatus(status?: string | null, outcome?: string | null): string {
  if (!status) return "Не начато";
  if (status === "completed") return outcome === "passed" ? "Зачтено" : "Не зачтено";
  return ({ in_progress: "В работе", under_review: "На проверке", technical_pause: "Техническая пауза" } as Record<string, string>)[status] ?? status;
}

export function trainingAction(status?: string | null): string {
  if (!status) return "Подготовить и начать";
  if (status === "in_progress" || status === "technical_pause") return "Продолжить";
  if (status === "under_review") return "Посмотреть отправленную работу";
  return "Посмотреть результат";
}

export function trainingDate(value?: string | null): string {
  return value ? new Date(value).toLocaleDateString("ru-RU", { timeZone: "Asia/Qyzylorda" }) : "—";
}

export function trainingDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString("ru-RU", { timeZone: "Asia/Qyzylorda" }) : "—";
}

export function groupTrainingResults(items: TrainingSummaryItem[]): Array<{ current: TrainingSummaryItem; history: TrainingSummaryItem[] }> {
  const groups = new Map<string, TrainingSummaryItem[]>();
  for (const item of items) {
    const key = `${item.course_code}\u0000${item.lesson_code}`;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return Array.from(groups.values()).map((versions) => {
    versions.sort((a, b) => b.course_version - a.course_version);
    return { current: versions[0], history: versions.slice(1) };
  });
}
