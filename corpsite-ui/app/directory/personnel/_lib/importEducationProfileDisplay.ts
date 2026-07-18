import type { PortfolioColumnPreview } from "./importApi.client";

export const EMPTY_PORTFOLIO_PREVIEW: PortfolioColumnPreview = {
  count: 0,
  items: [],
  extra_count: 0,
};

export function normalizePortfolioColumnPreview(
  preview: PortfolioColumnPreview | undefined,
  fallbackCount = 0
): PortfolioColumnPreview {
  if (preview) {
    return {
      count: preview.count ?? fallbackCount,
      items: Array.isArray(preview.items) ? preview.items.filter((item) => item.text?.trim()) : [],
      extra_count: preview.extra_count ?? Math.max(0, (preview.count ?? fallbackCount) - (preview.items?.length ?? 0)),
    };
  }
  return fallbackCount > 0
    ? { count: fallbackCount, items: [], extra_count: fallbackCount }
    : EMPTY_PORTFOLIO_PREVIEW;
}

export function renderPortfolioColumnPreview(preview: PortfolioColumnPreview | undefined): {
  primary: string;
  suffix: string | null;
} {
  const normalized = normalizePortfolioColumnPreview(preview);
  if (normalized.count <= 0 || normalized.items.length === 0) {
    return { primary: "Нет сведений", suffix: null };
  }
  const extra = normalized.extra_count > 0 ? `+${normalized.extra_count} ещё` : null;
  return { primary: normalized.items[0].text, suffix: extra };
}

export type TrainingContentFilter =
  | ""
  | "education"
  | "training"
  | "certificates"
  | "categories"
  | "empty";

export const TRAINING_CONTENT_FILTER_LABELS: Record<TrainingContentFilter, string> = {
  "": "Все типы сведений",
  education: "Образование",
  training: "Обучение",
  certificates: "Сертификаты",
  categories: "Категории",
  empty: "Без сведений",
};
