import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import MigrationStatusBlock from "./MigrationStatusBlock";

const statuses=["NOT_STARTED","PROCESSING","AUTO_READY","REVIEW_REQUIRED","CORRECTED_BY_HR","ACCEPTED","NO_SOURCE_DATA","NOT_APPLICABLE","BLOCKED","STALE","ERROR"];
describe("MigrationStatusBlock",()=>{
  afterEach(cleanup);
  it.each(statuses)("renders text status %s with reason and calculated time",(code)=>{
    render(<MigrationStatusBlock cell={{status_code:code,status_label:`Текст ${code}`,reason_code:"SAFE",reason_label:"Текст причины",calculated_at:"2026-01-01T00:00:00Z"}}/>);
    expect(screen.getByTestId("ppr-migration-status-block").textContent).toContain(code); expect(screen.getByTestId("ppr-migration-status-block").textContent).toContain("Текст причины"); expect(screen.getByTestId("ppr-migration-status-block").textContent).toContain("Рассчитано:");
  });
  it("renders nothing without projection",()=>{const {container}=render(<MigrationStatusBlock/>);expect(container.innerHTML).toBe("");});
});
