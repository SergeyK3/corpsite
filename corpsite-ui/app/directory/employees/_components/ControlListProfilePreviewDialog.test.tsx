import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import ControlListProfilePreviewDialog from "./ControlListProfilePreviewDialog";

afterEach(cleanup);

describe("ControlListProfilePreviewDialog", () => {
  it("shows read-only control-list profile data without write actions", () => {
    render(
      <ControlListProfilePreviewDialog
        open
        onClose={() => undefined}
        detail={{
          batch_id: 17,
          row_id: 501,
          full_name: "Anna Ivanova",
          iin: "900101300123",
          department_recoding: { org_unit_id: 7, org_unit_name: "HR Department", department_group: "Administration" },
          profile: {
            basic: {
              full_name: "Anna Ivanova",
              iin: "900101300123",
              birth_date: "1990-01-01",
              sex: "F",
              department_source: "HR Department",
              position_raw: "HR Manager",
              experience_raw: "10 years",
              employment_rate: 1,
              qualification_raw: "Senior",
              nationality: "Kazakh",
              phone_raw: "+7 700 000 0000",
            },
            education: {}, education_records: [], training_records: [], category_records: [], certificate_records: [], award_records: [],
            degrees: { candidate_medical_sciences: false, doctor_medical_sciences: false, raw_text: "", records: [] },
          },
        } as never}
      />,
    );

    expect(screen.getByText("Anna Ivanova")).toBeInTheDocument();
    expect(screen.getAllByText("HR Department")).toHaveLength(2);
    expect(screen.getByText("HR Manager")).toBeInTheDocument();
    expect(screen.getByText(/Предварительный просмотр данных контрольного списка/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /создать|сохранить|перенести/i })).not.toBeInTheDocument();
  });
});
