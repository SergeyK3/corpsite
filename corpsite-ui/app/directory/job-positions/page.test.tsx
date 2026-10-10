import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import JobPositionsPage from "./page";
import { apiFetchJson } from "@/lib/api";
vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));
afterEach(cleanup);
it("saves names and document form, then reopens the persisted catalog entry with immutable code", async () => {
  let job = { job_code: "NURSE", job_nameru: "Медсестра", job_namekk: "Мейіргер", job_namekk_doc: "мейіргері", legacy_position_ids: [25, 27] };
  vi.mocked(apiFetchJson).mockImplementation(async (_path, options) => {
    if (options?.method === "PUT") { job = { ...job, ...options.body }; return job as never; }
    return { items: [job], can_edit: true } as never;
  });
  render(<JobPositionsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Редактировать" }));
  fireEvent.change(screen.getByLabelText("Название RU"), { target: { value: "Медицинская сестра" } });
  fireEvent.change(screen.getByLabelText("Название KK"), { target: { value: "Мейірбике" } });
  fireEvent.change(screen.getByLabelText("Должность в тексте приказа KK"), { target: { value: "мейірбикесі" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
  await screen.findByRole("status");
  fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
  await waitFor(() => expect(screen.getByLabelText("Должность в тексте приказа KK")).toHaveValue("мейірбикесі"));
  expect(screen.getByLabelText("Название RU")).toHaveValue("Медицинская сестра");
  expect(apiFetchJson).toHaveBeenCalledWith("/directory/job-positions/NURSE", { method: "PUT", body: { job_nameru: "Медицинская сестра", job_namekk: "Мейірбике", job_namekk_doc: "мейірбикесі" } });
});
