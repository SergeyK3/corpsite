import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import PersonnelOrderDuplicateActions from "./PersonnelOrderDuplicateActions";

afterEach(cleanup);
const candidate = {order_id: 5647, order_number: "2 тест", order_date: "2026-01-05", order_type_code: "COMPOSITE", status: "DRAFT", record_quality: "WORKING", is_conflict: true};

it("opens a conflict of another type independently of journal filters", () => {
  render(<PersonnelOrderDuplicateActions day="2026-01-05" duplicate={{blocking: true, warnings: [], candidates: [{...candidate, can_open: true}]}} />);
  expect(screen.getByRole("link", {name: "Открыть существующий приказ"})).toHaveAttribute("href", "/directory/personnel/orders?order_id=5647&record_quality=ALL&include_closed=true");
  expect(screen.getByTestId("personnel-order-duplicate-actions")).toHaveTextContent("Рабочая запись");
  expect(screen.getByTestId("personnel-order-duplicate-actions")).toHaveTextContent("независимо от типа и фильтров журнала");
});

it.each([false, undefined])("does not offer an open action without explicit read permission (%s)", can_open => {
  render(<PersonnelOrderDuplicateActions day="2026-01-05" duplicate={{blocking: true, warnings: [], candidates: [{...candidate, can_open}]}} />);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("does not link a non-conflicting same-number order from another date", () => {
  render(<PersonnelOrderDuplicateActions day="2026-01-05" duplicate={{blocking: false, warnings: [], candidates: [{...candidate, is_conflict: false, can_open: true}]}} />);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
