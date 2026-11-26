const paragraphs = [
  "Анкету можно заполнить дома. Перед началом подготовьте фото и документы.",
  "На первом шаге понадобится фото 3×4 в формате JPEG, PNG или HEIC, размером до 10 МБ. Обрезать фото можно прямо в анкете.",
  "Заранее сохраните на устройстве PDF-копии документов, которые планируете приложить: диплома, сертификатов, свидетельств и других документов.",
] as const;

export const INTAKE_CANDIDATE_MEMO_TEXT = `Памятка кандидату\n\n${paragraphs.join("\n\n")}`;

export default function PersonnelApplicationIntakeMemo() {
  return (
    <section
      className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-100"
      data-testid="intake-candidate-memo"
    >
      <h3 className="font-semibold">Памятка кандидату</h3>
      {paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
    </section>
  );
}
