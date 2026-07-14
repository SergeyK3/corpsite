import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EmployeeCardDeletionNotice from "./EmployeeCardDeletionNotice";

describe("EmployeeCardDeletionNotice", () => {
  it("renders informational deletion notice without actions", () => {
    render(<EmployeeCardDeletionNotice />);

    const notice = screen.getByTestId("employee-card-deletion-notice");
    expect(notice.tagName).toBe("ASIDE");
    expect(notice).toHaveTextContent("Удаление сотрудника из справочника персонала");
    expect(notice).toHaveTextContent("модуле кадрового контура");
    expect(notice.querySelector("a")).toBeNull();
    expect(notice.querySelector("button")).toBeNull();
  });
});
