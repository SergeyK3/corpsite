import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import QualificationCategoryPreviewResult from "./QualificationCategoryPreviewResult";

afterEach(cleanup);
const previews = {
  ru: {title:"Категория RU",preamble:"Преамбула RU",directive:"ПРИКАЗЫВАЮ:",body:"Категория врача будет считаться высшей.",basis:"Основание: TEST сертификат.",footer:""},
  kk: {title:"Санат KK",preamble:"Кіріспе KK",directive:"БҰЙЫРАМЫН:",body:"Дәрігер санаты жоғары болып есептелсін.",basis:"Негіз: TEST сертификат.",footer:""},
};
it("renders both category languages using the shared personnel order document, including its complete footer",()=>{
  const original=JSON.stringify(previews);
  render(<QualificationCategoryPreviewResult previews={previews} templateId={42} templateVersionId={55}/>);
  for(const locale of ["ru","kk"] as const) {
    const column=within(screen.getByTestId(`category-order-document-${locale}`));
    const document=column.getByTestId("personnel-order-print-document");
    expect(document).toHaveAttribute("data-language",locale);
    expect(document).toHaveAttribute("data-category-document","true");
    expect(document.querySelector(".personnel-order-print-title")).toHaveTextContent(previews[locale].title);
    expect(document.querySelector(".personnel-order-print-preamble")).toHaveTextContent(previews[locale].preamble);
    expect(document.querySelector(".personnel-order-print-order-verb")).toHaveTextContent(previews[locale].directive);
    expect(document.querySelector(".personnel-order-print-item-body")).toHaveTextContent(previews[locale].body);
    expect(column.getByTestId("personnel-order-print-basis").textContent?.match(/TEST сертификат/g)).toHaveLength(1);
    expect(column.getByTestId("personnel-order-print-signature-line")).toBeInTheDocument();
    expect(column.getByTestId("personnel-order-print-acknowledgement")).toBeInTheDocument();
    expect(column.getByTestId("personnel-order-print-executor")).toHaveTextContent(locale==="ru"?"Исполнитель:":"Орындаушы:");
    expect(document).not.toHaveTextContent(previews[locale==="ru"?"kk":"ru"].body);
  }
  expect(JSON.stringify(previews)).toBe(original);
});
it("uses the same KK-left RU-right document layout throughout the category editor",()=>{
  render(<QualificationCategoryPreviewResult previews={previews} templateId={41} templateVersionId={54}/>);
  expect(screen.getAllByTestId("personnel-order-print-document")).toHaveLength(2);
  expect(screen.getByTestId("category-preview").children[0]).toHaveAttribute("lang","kk");
  expect(screen.getByTestId("category-preview").children[1]).toHaveAttribute("lang","ru");
});
