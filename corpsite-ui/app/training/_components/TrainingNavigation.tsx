"use client";

import Link from "next/link";
import { useCurrentUser } from "@/lib/currentUser";

export default function TrainingNavigation({ active }: { active: "lessons" | "results" | "progress" | "expert" }) {
  const me = useCurrentUser();
  const item = (href: string, label: string, selected: boolean) =>
    <Link href={href} aria-current={selected ? "page" : undefined}
      className={`rounded-lg px-3 py-2 text-sm font-medium ${selected ? "bg-blue-700 text-white" : "border border-zinc-300 text-blue-700 dark:border-zinc-700"}`}>{label}</Link>;
  return <nav aria-label="Навигация обучения" className="flex flex-wrap gap-2">
    {item("/training", "Мои занятия", active === "lessons")}
    {item("/training/results", "Мои результаты", active === "results")}
    {item("/training/progress", "Мой прогресс", active === "progress")}
    {me?.has_learning_expert === true && item("/training/expert", "Внутреннее обучение", active === "expert")}
    {me?.training_enabled === true && me?.has_learning_review === true && item("/training/review", "Проверка работ", false)}
  </nav>;
}
