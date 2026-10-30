"use client";
import { useEffect, useState } from "react";
import { apiFetchJson } from "@/lib/api";
import { loadOrgUnitSelectOptions, type OrgUnitSelectOption } from "@/lib/orgUnitsSelect";

export type EducationOrderReference = { code: string; name_ru: string; name_kk: string | null; is_active: boolean };
type Specialty = { medical_specialty_id: number; name: string; name_kk: string | null; is_active: boolean };

export function useEducationOrderCatalogs() {
  const [levels, setLevels] = useState<EducationOrderReference[]>([]);
  const [kinds, setKinds] = useState<EducationOrderReference[]>([]);
  const [specialties, setSpecialties] = useState<EducationOrderReference[]>([]);
  const [units, setUnits] = useState<OrgUnitSelectOption[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    const references = async (path: string) => {
      const response = await apiFetchJson<{ items: EducationOrderReference[]; schema_ready: boolean }>(path, { query: { state: "active" } });
      if (!response.schema_ready) throw new Error("Справочник ещё не подготовлен.");
      return response.items.filter(row => row.is_active);
    };
    const medical = async () => {
      const result: EducationOrderReference[] = [];
      let offset = 0;
      while (true) {
        const page = await apiFetchJson<{ items: Specialty[]; total: number }>("/directory/medical-specialties", { query: { is_active: true, limit: 1000, offset } });
        result.push(...page.items.filter(row => row.is_active).map(row => ({ code: String(row.medical_specialty_id), name_ru: row.name, name_kk: row.name_kk, is_active: row.is_active })));
        offset += page.items.length;
        if (!page.items.length || offset >= page.total) return result;
      }
    };
    void Promise.allSettled([
      references("/api/ppr/education-levels"), references("/api/ppr/document-kinds"), medical(), loadOrgUnitSelectOptions(),
    ]).then(([levelResult, kindResult, specialtyResult, unitResult]) => {
      if (!live) return;
      if (levelResult.status === "fulfilled") setLevels(levelResult.value);
      if (kindResult.status === "fulfilled") setKinds(kindResult.value);
      if (specialtyResult.status === "fulfilled") setSpecialties(specialtyResult.value);
      if (unitResult.status === "fulfilled") setUnits(unitResult.value);
      setErrors([levelResult, kindResult, specialtyResult, unitResult].flatMap((result, index) => result.status === "rejected" ? [`Не удалось загрузить: ${["уровни образования", "виды документов", "медицинские специальности", "подразделения"][index]}. Сохранённые значения оставлены без изменений.`] : []));
      setLoading(false);
    });
    return () => { live = false; };
  }, []);
  return { levels, kinds, specialties, units, errors, loading };
}
