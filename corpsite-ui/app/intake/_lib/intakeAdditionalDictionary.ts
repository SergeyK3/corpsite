/** Controlled vocabularies for intake step «Дополнительные сведения». */

export const INTAKE_FOREIGN_LANGUAGE_OTHER = "Другой язык";

export const INTAKE_FOREIGN_LANGUAGE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "Английский", label: "Английский" },
  { value: "Казахский", label: "Казахский" },
  { value: "Русский", label: "Русский" },
  { value: "Немецкий", label: "Немецкий" },
  { value: "Французский", label: "Французский" },
  { value: "Турецкий", label: "Турецкий" },
  { value: "Китайский", label: "Китайский" },
  { value: INTAKE_FOREIGN_LANGUAGE_OTHER, label: INTAKE_FOREIGN_LANGUAGE_OTHER },
];

export const INTAKE_FOREIGN_LANGUAGE_PROFICIENCY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "Начальный (A1)", label: "Начальный (A1)" },
  { value: "Элементарный (A2)", label: "Элементарный (A2)" },
  { value: "Средний (B1)", label: "Средний (B1)" },
  { value: "Выше среднего (B2)", label: "Выше среднего (B2)" },
  { value: "Продвинутый (C1)", label: "Продвинутый (C1)" },
  { value: "Владение в совершенстве (C2)", label: "Владение в совершенстве (C2)" },
];

export const INTAKE_AWARD_OTHER = "Другая";

export const INTAKE_AWARD_CATEGORY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "Государственная", label: "Государственная" },
  { value: "Ведомственная", label: "Ведомственная" },
  { value: "Почётная грамота", label: "Почётная грамота" },
  { value: "Благодарность", label: "Благодарность" },
  { value: "Нагрудный знак", label: "Нагрудный знак" },
  { value: "Медаль", label: "Медаль" },
  { value: INTAKE_AWARD_OTHER, label: INTAKE_AWARD_OTHER },
];

export const INTAKE_AWARD_NAME_POPULAR: readonly string[] = [
  "Орден «Парасат»",
  "Орден «Достық»",
  "Медаль «Еren enbegi ushin»",
  "Почётная грамота Министерства здравоохранения",
  "Благодарность Министерства здравоохранения",
  "Нагрудный знак «Отличник здравоохранения»",
  "Юбилейная медаль «30 лет Независимости»",
];

export const INTAKE_AWARD_NAME_CATALOG: readonly string[] = [
  ...INTAKE_AWARD_NAME_POPULAR,
  "Почётная грамота акима",
  "Благодарность акима",
  "Нагрудный знак «За высокие достижения в труде»",
  "Медаль «За доблестный труд»",
];

export const INTAKE_ACADEMIC_DEGREE_OTHER = "Другое";

export const INTAKE_ACADEMIC_DEGREE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "Кандидат наук", label: "Кандидат наук" },
  { value: "Доктор наук", label: "Доктор наук" },
  { value: "PhD", label: "PhD" },
  { value: "Доктор по профилю", label: "Доктор по профилю" },
  { value: INTAKE_ACADEMIC_DEGREE_OTHER, label: INTAKE_ACADEMIC_DEGREE_OTHER },
];

export const INTAKE_ACADEMIC_TITLE_OTHER = "Другое";

export const INTAKE_ACADEMIC_TITLE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "Доцент", label: "Доцент" },
  { value: "Профессор", label: "Профессор" },
  { value: "Ассоциированный профессор", label: "Ассоциированный профессор" },
  { value: INTAKE_ACADEMIC_TITLE_OTHER, label: INTAKE_ACADEMIC_TITLE_OTHER },
];

export const INTAKE_FIELD_OF_SCIENCE_POPULAR: readonly string[] = [
  "Медицина",
  "Юриспруденция",
  "Экономика",
  "Педагогика",
  "Филология",
  "Инженерия",
  "Биология",
  "Химия",
  "Физика",
  "История",
  "Психология",
  "Социология",
  "Политология",
  "Информатика",
];

export const INTAKE_FIELD_OF_SCIENCE_CATALOG: readonly string[] = [
  ...INTAKE_FIELD_OF_SCIENCE_POPULAR,
  "Фармация",
  "Сестринское дело",
  "Менеджмент",
  "Маркетинг",
  "Финансы",
  "Бухгалтерский учёт",
  "Архитектура",
  "Строительство",
];
