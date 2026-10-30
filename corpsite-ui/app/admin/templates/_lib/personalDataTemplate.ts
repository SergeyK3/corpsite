export const PERSONAL_DATA_TEMPLATE_TYPE = "PERSONAL_DATA_CHANGE";
const labels: Record<string, string> = {
  title_ru: "Название RU", title_kk: "Название KK", print_title_ru: "Печатный заголовок RU", print_title_kk: "Печатный заголовок KK",
  preamble_ru: "Преамбула RU", preamble_kk: "Преамбула KK", body_template_ru: "Текст приказа RU", body_template_kk: "Текст приказа KK",
  basis_template_ru: "Основание RU", basis_template_kk: "Основание KK",
};
export function personalDataTemplateIssues(values: Record<string, string | null | undefined>): string[] {
  return Object.entries(labels).flatMap(([key, label]) => {
    const value = values[key] || "";
    if (!value.trim()) return [`Заполните поле «${label}».`];
    if (/\[[^\]\n]+\]/.test(value)) return [`«${label}»: замените редакционные placeholders в квадратных скобках на переменные шаблона.`];
    if (/<\s*\/?\s*(?:script|style)|javascript:|=>|\b(?:if|for|function)\s*\(/i.test(value)) return [`«${label}»: удалите небезопасное содержимое.`];
    return [];
  });
}
