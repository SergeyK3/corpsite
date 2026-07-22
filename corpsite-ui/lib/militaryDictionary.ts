/** Military dictionaries: compositions, ranks, normalization and filtering rules. */

export type IntakeMilitaryCompositionValue =
  | "soldiers"
  | "sergeants"
  | "officers"
  | "senior_officers"
  | "other";

export type IntakeMilitaryComboboxOption = {
  value: string;
  label: string;
};

export type IntakeMilitaryDraftFields = {
  status: string;
  rank: string;
  category: string;
  composition: string;
  specialty_code: string;
  specialty_name: string;
  fitness_category: string;
  commissariat: string;
  registration_group: string;
  registration_category: string;
};

export type PprMilitaryCompositionFields = {
  personnel_composition: string;
  military_rank: string;
};

export const INTAKE_MILITARY_COMPOSITION_OPTIONS: ReadonlyArray<{
  value: IntakeMilitaryCompositionValue;
  label: string;
}> = [
  { value: "soldiers", label: "Рядовой состав" },
  { value: "sergeants", label: "Сержантский состав" },
  { value: "officers", label: "Офицерский состав" },
  { value: "senior_officers", label: "Командный состав" },
  { value: "other", label: "Иной состав" },
];

export const INTAKE_MILITARY_OTHER_RANK_OPTION = "Другое";

export const INTAKE_MILITARY_RANKS_BY_COMPOSITION: Readonly<
  Record<IntakeMilitaryCompositionValue, readonly string[]>
> = {
  soldiers: ["Рядовой", "Ефрейтор"],
  sergeants: [
    "Младший сержант",
    "Сержант",
    "Старший сержант",
    "Сержант 3 класса",
    "Сержант 2 класса",
    "Сержант 1 класса",
    "Штаб-сержант",
    "Мастер-сержант",
  ],
  officers: [
    "Лейтенант",
    "Старший лейтенант",
    "Капитан",
    "Майор",
    "Подполковник",
    "Полковник",
  ],
  senior_officers: [
    "Генерал-майор",
    "Генерал-лейтенант",
    "Генерал-полковник",
    "Генерал",
  ],
  other: [INTAKE_MILITARY_OTHER_RANK_OPTION],
};

const COMPOSITION_LABEL_TO_VALUE: Record<string, IntakeMilitaryCompositionValue> = {
  soldiers: "soldiers",
  sergeants: "sergeants",
  officers: "officers",
  senior_officers: "senior_officers",
  command: "senior_officers",
  other: "other",
  "рядовой состав": "soldiers",
  "рядовой и сержантский состав": "soldiers",
  "сержантский состав": "sergeants",
  "офицерский состав": "officers",
  "высший офицерский состав": "senior_officers",
  "командный состав": "senior_officers",
  "иной состав": "other",
};

const CANONICAL_COMPOSITION_VALUES = new Set<string>(
  INTAKE_MILITARY_COMPOSITION_OPTIONS.map((option) => option.value),
);

const RANK_TO_COMPOSITION = buildRankToCompositionMap();

function buildRankToCompositionMap(): Map<string, IntakeMilitaryCompositionValue> {
  const map = new Map<string, IntakeMilitaryCompositionValue>();
  for (const [composition, ranks] of Object.entries(INTAKE_MILITARY_RANKS_BY_COMPOSITION) as Array<
    [IntakeMilitaryCompositionValue, readonly string[]]
  >) {
    if (composition === "other") continue;
    for (const rank of ranks) {
      map.set(normalizeLookupKey(rank), composition);
    }
  }
  return map;
}

function normalizeLookupKey(value: string): string {
  return value.trim().toLowerCase();
}

export function normalizeIntakeDictionaryQuery(query: string): string {
  return query.trim().toLowerCase();
}

export const INTAKE_MILITARY_COMPOSITION_CATALOG: IntakeMilitaryComboboxOption[] =
  INTAKE_MILITARY_COMPOSITION_OPTIONS.map((option) => ({
    value: option.value,
    label: option.label,
  }));

export function intakeMilitaryCompositionCatalog(): IntakeMilitaryComboboxOption[] {
  return INTAKE_MILITARY_COMPOSITION_CATALOG;
}

export function normalizeIntakeMilitaryComposition(value: string): IntakeMilitaryCompositionValue | "" {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (CANONICAL_COMPOSITION_VALUES.has(trimmed)) return trimmed as IntakeMilitaryCompositionValue;
  const mapped = COMPOSITION_LABEL_TO_VALUE[normalizeLookupKey(trimmed)];
  return mapped ?? "";
}

export function intakeMilitaryCompositionLabel(value: string): string {
  const normalized = normalizeIntakeMilitaryComposition(value);
  if (!normalized) return value.trim();
  return (
    INTAKE_MILITARY_COMPOSITION_OPTIONS.find((option) => option.value === normalized)?.label ?? value.trim()
  );
}

export function inferIntakeMilitaryCompositionFromRank(rank: string): IntakeMilitaryCompositionValue | "" {
  const trimmed = rank.trim();
  if (!trimmed) return "";
  const mapped = RANK_TO_COMPOSITION.get(normalizeLookupKey(trimmed));
  if (mapped) return mapped;
  if (normalizeLookupKey(trimmed) === normalizeLookupKey(INTAKE_MILITARY_OTHER_RANK_OPTION)) {
    return "other";
  }
  return "other";
}

export function getIntakeMilitaryRankOptions(
  compositionRaw: string,
): IntakeMilitaryComboboxOption[] {
  const composition = normalizeIntakeMilitaryComposition(compositionRaw);
  if (!composition) return [];
  return INTAKE_MILITARY_RANKS_BY_COMPOSITION[composition].map((rank) => ({
    value: rank,
    label: rank,
  }));
}

export function filterIntakeMilitaryComboboxOptions(
  options: readonly IntakeMilitaryComboboxOption[],
  query: string,
): IntakeMilitaryComboboxOption[] {
  const normalizedQuery = normalizeIntakeDictionaryQuery(query);
  if (!normalizedQuery) return [...options];
  return options.filter((option) => {
    const lowerLabel = option.label.toLowerCase();
    if (lowerLabel.includes(normalizedQuery)) return true;
    return lowerLabel.split(/[\s-]+/).some((word) => word.startsWith(normalizedQuery));
  });
}

export function resolveIntakeMilitaryComboboxSelection(
  query: string,
  options: readonly IntakeMilitaryComboboxOption[],
): string | null {
  const trimmed = query.trim();
  if (!trimmed) return null;
  const normalized = normalizeLookupKey(trimmed);
  const exactValue = options.find((option) => normalizeLookupKey(option.value) === normalized);
  if (exactValue) return exactValue.value;
  const exactLabel = options.find((option) => normalizeLookupKey(option.label) === normalized);
  if (exactLabel) return exactLabel.value;
  return null;
}

export function isIntakeMilitaryRankCompatible(
  compositionRaw: string,
  rankRaw: string,
): boolean {
  const composition = normalizeIntakeMilitaryComposition(compositionRaw);
  const rank = rankRaw.trim();
  if (!composition || !rank) return !rank;
  if (composition === "other") return true;
  return INTAKE_MILITARY_RANKS_BY_COMPOSITION[composition].some(
    (option) => normalizeLookupKey(option) === normalizeLookupKey(rank),
  );
}

export function applyIntakeMilitaryCompositionChange(
  nextCompositionRaw: string,
  currentRank: string,
): Pick<IntakeMilitaryDraftFields, "composition" | "rank"> {
  const composition = normalizeIntakeMilitaryComposition(nextCompositionRaw);
  if (!composition) {
    return { composition: "", rank: "" };
  }
  const rank = currentRank.trim();
  if (!rank || isIntakeMilitaryRankCompatible(composition, rank)) {
    return { composition, rank };
  }
  return { composition, rank: "" };
}

export function applyPprMilitaryCompositionChange(
  nextCompositionRaw: string,
  currentRank: string,
): PprMilitaryCompositionFields {
  const { composition, rank } = applyIntakeMilitaryCompositionChange(nextCompositionRaw, currentRank);
  return { personnel_composition: composition, military_rank: rank };
}

export function reconcileIntakeMilitaryDraftOnLoad(
  military: IntakeMilitaryDraftFields,
): IntakeMilitaryDraftFields {
  const normalizedComposition = normalizeIntakeMilitaryComposition(military.composition);
  if (normalizedComposition) {
    return {
      ...military,
      composition: normalizedComposition,
      specialty_name: military.specialty_name ?? "",
    };
  }
  const rank = military.rank.trim();
  if (!rank) {
    return { ...military, composition: "", specialty_name: military.specialty_name ?? "" };
  }
  return {
    ...military,
    composition: inferIntakeMilitaryCompositionFromRank(rank),
    specialty_name: military.specialty_name ?? "",
  };
}

export function reconcilePprMilitaryFormFields(
  fields: PprMilitaryCompositionFields,
): PprMilitaryCompositionFields {
  const normalizedComposition = normalizeIntakeMilitaryComposition(fields.personnel_composition);
  if (normalizedComposition) {
    return {
      personnel_composition: normalizedComposition,
      military_rank: fields.military_rank.trim(),
    };
  }
  const rank = fields.military_rank.trim();
  if (!rank) {
    return { personnel_composition: "", military_rank: "" };
  }
  return {
    personnel_composition: inferIntakeMilitaryCompositionFromRank(rank),
    military_rank: rank,
  };
}

export function intakeMilitaryComboboxDisplayLabel(
  value: string,
  options: readonly IntakeMilitaryComboboxOption[],
): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const match = options.find(
    (option) =>
      normalizeLookupKey(option.value) === normalizeLookupKey(trimmed) ||
      normalizeLookupKey(option.label) === normalizeLookupKey(trimmed),
  );
  return match?.label ?? trimmed;
}
