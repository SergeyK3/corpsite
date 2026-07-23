"use client";

import {
  formatIntakeAcademicDegreeDateCell,
  formatIntakeAwardDateCell,
  intakeAdditionalCellValue,
  normalizeIntakeAcademicDegreeEntry,
  normalizeIntakeAcademicTitleEntry,
  normalizeIntakeAwardEntry,
  normalizeIntakeForeignLanguageEntry,
  resolveIntakeAcademicDegreeDisplay,
  resolveIntakeAcademicTitleDisplay,
  resolveIntakeAwardCategoryDisplay,
  resolveIntakeAwardNameDisplay,
  resolveIntakeForeignLanguageDisplay,
} from "@/app/intake/_lib/intakeAdditional";
import type {
  PprAdditionalAcademicDegreeResponse,
  PprAdditionalAcademicTitleResponse,
  PprAdditionalAwardResponse,
  PprAdditionalForeignLanguageResponse,
  PprAdditionalProfileResponse,
} from "../_lib/pprQueryTypes";

type Props = {
  additional: PprAdditionalProfileResponse;
};

function NoneDeclaredMessage({ label }: { label: string }) {
  return <p className="text-sm text-zinc-500">{label}: нет сведений.</p>;
}

function EmptyRecordsMessage({ label }: { label: string }) {
  return <p className="text-sm text-zinc-500">{label}: записей пока нет.</p>;
}

function ForeignLanguagesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalForeignLanguageResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Иностранные языки" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Иностранные языки" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="ppr-additional-languages-table">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Язык</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Уровень владения
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeForeignLanguageEntry(item);
            return (
              <tr key={`ppr-language-${index}`} data-testid={`ppr-additional-language-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeForeignLanguageDisplay(normalized.language)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.proficiency)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AwardsBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAwardResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Награды" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Награды" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="ppr-additional-awards-table">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Название награды
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Кем выдана</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">№ документа</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAwardEntry(item);
            return (
              <tr key={`ppr-award-${index}`} data-testid={`ppr-additional-award-row-${index}`}>
                <td className="px-3 py-2 text-sm">
                  <div>{resolveIntakeAwardNameDisplay(normalized)}</div>
                  {normalized.category ? (
                    <div className="mt-0.5 text-xs text-zinc-500">{resolveIntakeAwardCategoryDisplay(normalized)}</div>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.issued_by)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">{formatIntakeAwardDateCell(normalized.awarded_at)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AcademicDegreesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAcademicDegreeResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Учёные степени" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Учёные степени" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table
        className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800"
        data-testid="ppr-additional-degrees-table"
      >
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Степень</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Область наук
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              № документа
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAcademicDegreeEntry({
              ...item,
              label: item.label ?? undefined,
              degree_type: item.degree_type ?? undefined,
            });
            return (
              <tr key={`ppr-degree-${index}`} data-testid={`ppr-additional-degree-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeAcademicDegreeDisplay(normalized)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.field_of_science)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">
                  {formatIntakeAcademicDegreeDateCell(normalized.completed_at)}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AcademicTitlesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAcademicTitleResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Учёные звания" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Учёные звания" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table
        className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800"
        data-testid="ppr-additional-titles-table"
      >
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Звание</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Область наук
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              № документа
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAcademicTitleEntry({
              ...item,
              label: item.label ?? undefined,
              degree_type: item.degree_type ?? undefined,
            });
            return (
              <tr key={`ppr-title-${index}`} data-testid={`ppr-additional-title-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeAcademicTitleDisplay(normalized)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.field_of_science)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">
                  {formatIntakeAcademicDegreeDateCell(normalized.completed_at)}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function PprCardAdditionalSection({ additional }: Props) {
  return (
    <div className="space-y-8" data-testid="ppr-additional-section">
      <section className="space-y-3" data-testid="ppr-additional-languages-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Знание иностранных языков</h3>
        <ForeignLanguagesBlock
          items={additional.foreign_languages}
          declaredEmpty={additional.foreign_languages_none}
        />
      </section>

      <section className="space-y-3" data-testid="ppr-additional-awards-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Награды</h3>
        <AwardsBlock items={additional.awards} declaredEmpty={additional.awards_none} />
      </section>

      <section className="space-y-3" data-testid="ppr-additional-degrees-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Учёные степени</h3>
        <AcademicDegreesBlock items={additional.academic_degrees} declaredEmpty={additional.academic_degrees_none} />
      </section>

      <section className="space-y-3" data-testid="ppr-additional-titles-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Учёные звания</h3>
        <AcademicTitlesBlock items={additional.academic_titles} declaredEmpty={additional.academic_titles_none} />
      </section>
    </div>
  );
}
