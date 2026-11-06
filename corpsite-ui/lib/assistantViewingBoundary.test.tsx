import React from "react";
import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import DocumentationViewingBoundary from "../components/DocumentationViewingBoundary";

afterEach(cleanup);

it("hides assistant dictionary changes while allowing Excel", () => {
  const change = vi.fn(), download = vi.fn();
  render(<DocumentationViewingBoundary assistant>
    <button onClick={change}>Создать должность</button>
    <button onClick={download}>Выгрузить в Excel</button>
  </DocumentationViewingBoundary>);
  expect((screen.getByText("Создать должность") as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText("Создать должность")).not.toBeVisible();
  expect(screen.queryByRole("button",{name:"Создать должность"})).toBeNull();
  fireEvent.click(screen.getByText("Выгрузить в Excel"));
  expect(download).toHaveBeenCalledOnce();
  expect(change).not.toHaveBeenCalled();
});

it("allows assistant search forms while keeping mutation submissions blocked",()=>{
  const search=vi.fn(event=>event.preventDefault()),save=vi.fn(event=>event.preventDefault());
  render(<DocumentationViewingBoundary assistant>
    <form onSubmit={search}><button type="submit">Обновить</button></form>
    <form onSubmit={save}><button type="submit">Сохранить</button></form>
  </DocumentationViewingBoundary>);
  fireEvent.click(screen.getByText("Обновить"));
  fireEvent.submit(screen.getByText("Сохранить").closest("form")!);
  expect(search).toHaveBeenCalledOnce();
  expect(save).not.toHaveBeenCalled();
});

it("retains the viewer's form exploration and prevents saving", () => {
  const create = vi.fn(), save = vi.fn();
  render(<DocumentationViewingBoundary>
    <button onClick={create}>Создать должность</button>
    <button onClick={save}>Сохранить</button>
  </DocumentationViewingBoundary>);
  fireEvent.click(screen.getByText("Создать должность"));
  fireEvent.click(screen.getByText("Сохранить"));
  expect(create).toHaveBeenCalledOnce();
  expect(save).not.toHaveBeenCalled();
});
