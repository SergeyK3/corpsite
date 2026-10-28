import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import QualificationCategoryTemplatePreview from "./QualificationCategoryTemplatePreview";
import { previewPersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

vi.mock("../_lib/personnelOrderTemplatesApi.client", async () => ({
  ...await vi.importActual<object>("../_lib/personnelOrderTemplatesApi.client"), previewPersonnelOrderTemplateDraft: vi.fn(),
}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const values={title_ru:"RU",title_kk:"KK",preamble_ru:"RU preamble",preamble_kk:"KK preamble",body_template_ru:"{{effective_date.ru}}",body_template_kk:"{{effective_date.kk}}",basis_template_ru:"RU basis",basis_template_kk:"KK basis"};
const previews={ru:{title:"RU",preamble:"RU preamble",body:"11.06.2026",basis:"RU basis",directive:"ПРИКАЗЫВАЮ:",footer:""},kk:{title:"KK",preamble:"KK preamble",body:"2026 жылғы 11 маусымнан",basis:"KK basis",directive:"БҰЙЫРАМЫН:",footer:""}};
it("automatically renders synthetic data without employee or department inputs and refreshes on request",async()=>{
  vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValue({previews});
  const view=render(<QualificationCategoryTemplatePreview values={values} refresh={0}/>);
  await screen.findByTestId("category-preview");
  expect(previewPersonnelOrderTemplateDraft).toHaveBeenCalledWith("QUALIFICATION_CATEGORY",values);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByTestId("category-preview").children[0]).toHaveAttribute("lang","kk");
  view.rerender(<QualificationCategoryTemplatePreview values={values} refresh={1}/>);
  await waitFor(()=>expect(previewPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(2));
});
it("ignores late results belonging to earlier editor text",async()=>{
  let finish!: (value:{previews:typeof previews})=>void;
  vi.mocked(previewPersonnelOrderTemplateDraft).mockReturnValueOnce(new Promise(resolve=>{finish=resolve;}));
  vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValue({previews:{...previews,ru:{...previews.ru,title:"Latest RU"}}});
  const view=render(<QualificationCategoryTemplatePreview values={values} refresh={0}/>);
  await waitFor(()=>expect(previewPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(1));
  view.rerender(<QualificationCategoryTemplatePreview values={{...values,title_ru:"Latest RU"}} refresh={0}/>);
  await screen.findByText("Latest RU");finish({previews});
  await waitFor(()=>expect(screen.getByTestId("category-order-document-ru")).toHaveTextContent("Latest RU"));
});
