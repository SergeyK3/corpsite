"use client";

import IntakeAcademicDegreesTable from "./IntakeAcademicDegreesTable";
import IntakeAcademicTitlesTable from "./IntakeAcademicTitlesTable";
import IntakeAwardsTable from "./IntakeAwardsTable";
import IntakeForeignLanguagesTable from "./IntakeForeignLanguagesTable";
import { INTAKE_SUPPORTS_ACADEMIC_DEGREES } from "../_lib/intakeApi.client";
import type { IntakeAdditionalPayload } from "../_lib/intakeApi.client";

type Props = {
  value: IntakeAdditionalPayload;
  onChange: (value: IntakeAdditionalPayload) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

export default function IntakeAdditionalStep({
  value,
  onChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const patch = (partial: Partial<IntakeAdditionalPayload>) => onChange({ ...value, ...partial });

  return (
    <div className="space-y-8" data-testid="intake-additional-step">
      <IntakeForeignLanguagesTable
        items={value.foreign_languages}
        declaredEmpty={value.foreign_languages_none}
        readOnly={readOnly}
        focusTestId={focusTestId}
        onChange={(items) =>
          patch({
            foreign_languages: items,
            foreign_languages_none: items.length > 0 ? false : value.foreign_languages_none,
          })
        }
        onDeclaredEmptyChange={(declaredEmpty) =>
          patch({
            foreign_languages_none: declaredEmpty,
            foreign_languages: declaredEmpty ? [] : value.foreign_languages,
          })
        }
      />

      <IntakeAwardsTable
        items={value.awards}
        declaredEmpty={value.awards_none}
        readOnly={readOnly}
        focusTestId={focusTestId}
        onChange={(items) =>
          patch({ awards: items, awards_none: items.length > 0 ? false : value.awards_none })
        }
        onDeclaredEmptyChange={(declaredEmpty) =>
          patch({
            awards_none: declaredEmpty,
            awards: declaredEmpty ? [] : value.awards,
          })
        }
      />

      {INTAKE_SUPPORTS_ACADEMIC_DEGREES ? (
        <>
          <IntakeAcademicDegreesTable
            items={value.academic_degrees}
            declaredEmpty={value.academic_degrees_none}
            readOnly={readOnly}
            focusTestId={focusTestId}
            onChange={(items) =>
              patch({
                academic_degrees: items,
                academic_degrees_none: items.length > 0 ? false : value.academic_degrees_none,
              })
            }
            onDeclaredEmptyChange={(declaredEmpty) =>
              patch({
                academic_degrees_none: declaredEmpty,
                academic_degrees: declaredEmpty ? [] : value.academic_degrees,
              })
            }
          />
          <IntakeAcademicTitlesTable
            items={value.academic_titles}
            declaredEmpty={value.academic_titles_none}
            readOnly={readOnly}
            focusTestId={focusTestId}
            onChange={(items) =>
              patch({
                academic_titles: items,
                academic_titles_none: items.length > 0 ? false : value.academic_titles_none,
              })
            }
            onDeclaredEmptyChange={(declaredEmpty) =>
              patch({
                academic_titles_none: declaredEmpty,
                academic_titles: declaredEmpty ? [] : value.academic_titles,
              })
            }
          />
        </>
      ) : null}
    </div>
  );
}
