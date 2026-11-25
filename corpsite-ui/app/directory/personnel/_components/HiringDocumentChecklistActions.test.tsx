import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CurrentUserProvider } from "@/lib/currentUser";
import HiringDocumentChecklistActions from "./HiringDocumentChecklistActions";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("opens both relative checklist addresses in new tabs for an HR head", () => {
  const open = vi.spyOn(window, "open").mockImplementation(() => null);
  render(<CurrentUserProvider value={{ role_code: "HR_HEAD" }}>
    <HiringDocumentChecklistActions testIdPrefix="electronic-hire" />
  </CurrentUserProvider>);

  fireEvent.click(screen.getByTestId("electronic-hire-print-checklist"));
  fireEvent.click(screen.getByTestId("electronic-hire-edit-checklist"));
  expect(open).toHaveBeenNthCalledWith(1, "/directory/personnel/hiring-document-checklist", "_blank", "noopener,noreferrer");
  expect(open).toHaveBeenNthCalledWith(2, "/directory/personnel/hiring-document-checklist?edit=1", "_blank", "noopener,noreferrer");
});

it("hides template editing without the same registration-window permission", () => {
  render(<CurrentUserProvider value={{ role_code: "STAFF" }}>
    <HiringDocumentChecklistActions testIdPrefix="electronic-hire" />
  </CurrentUserProvider>);

  expect(screen.getByTestId("electronic-hire-print-checklist")).toBeInTheDocument();
  expect(screen.queryByTestId("electronic-hire-edit-checklist")).not.toBeInTheDocument();
});
