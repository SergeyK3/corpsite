import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MigrationDomainCard from "./MigrationDomainCard";

const domain = (code: "education" | "category") => {
  const isCategory = code === "category";
  return {
  domain_code: code,
  display_name: isCategory ? "Категория" : "Образование",
  description: null,
  is_enabled: isCategory,
  target_table_names: [],
  control_list_columns: [],
  created_at: null,
  updated_at: null,
  };
};

describe("MigrationDomainCard", () => {
  it("shows education awaiting enablement and disables action", () => {
    render(<MigrationDomainCard domain={domain("education")} />);
    expect(screen.getByText("Ожидает включения")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Начать перенос" })).toBeDisabled();
  });

  it("labels category as not implemented", () => {
    render(<MigrationDomainCard domain={domain("category")} />);
    expect(screen.getByText("Перенос пока не реализован")).toBeInTheDocument();
  });
});
