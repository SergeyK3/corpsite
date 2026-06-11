// FILE: corpsite-ui/lib/diLibraries.ts
// Временный статический маппинг библиотек ДИ.
// Следующий этап: справочник «Библиотеки ДИ» с UI для администрирования.

const DEPARTMENT_DI_LIBRARY_BY_UNIT_ID: Record<number, string> = {
  // ОВЭиПД / отдел экспертизы (пилот)
  44: "https://drive.google.com/drive/folders/1zx-9CU3RgN0923PZsmzJRs6bvAfAGrnw?usp=sharing",
};

const SECTION_DI_LIBRARY_BY_LOGIN: Record<string, string> = {
  "qm_head@corp.local": "https://drive.google.com/drive/folders/1fjIH48c1mxjFGoIdgXTaXy3VlxezyQVH?usp=sharing",
  "qm_complaint_reg@corp.local": "https://drive.google.com/drive/folders/1biiCNC9aut8e0nS2khJ37udtiPoNQibA?usp=sharing",
  "qm_hosp@corp.local": "https://drive.google.com/drive/folders/1sK5Xf7-Yb2236_tHYCckAUkP4EXbfsq5?usp=sharing",
  "qm_amb@corp.local": "https://drive.google.com/drive/folders/1-Y7P9cYvLL1ro-GqH7IiZhPeWPB6ZoYK?usp=sharing",
  "qm_complaint_pat@corp.local": "https://drive.google.com/drive/folders/1FRKWjccKl63l267OAO9wEGMrRk72tAoX?usp=sharing",
  "qm_intern_educat@corp.local": "https://drive.google.com/drive/folders/19e08DUB4Mh4sUlAZPGJdri260d2KpCfG?usp=sharing",
};

export function getDepartmentDiLibraryUrl(unitId: number | undefined | null): string | null {
  const id = Number(unitId ?? 0);
  if (!Number.isFinite(id) || id <= 0) return null;
  return DEPARTMENT_DI_LIBRARY_BY_UNIT_ID[id] ?? null;
}

export function getSectionDiLibraryUrl(login: string | undefined | null): string | null {
  const key = String(login ?? "").trim().toLowerCase();
  return key ? SECTION_DI_LIBRARY_BY_LOGIN[key] ?? null : null;
}
