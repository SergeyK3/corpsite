import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import PersonnelOrderDateFilter, {parsePersonnelFilterDate} from "./PersonnelOrderDateFilter";

afterEach(cleanup);

it("keeps each incomplete date and commits only a complete valid calendar date", () => {
  const commit = vi.fn();
  const view = render(<PersonnelOrderDateFilter label="Дата с" onCommit={commit} />);
  const input = screen.getByLabelText("Дата с");
  input.focus();
  let text = "";
  for (const character of "05.01.2020") {
    text += character;
    fireEvent.change(input, {target: {value: text}});
    expect(input).toHaveValue(text);
    if (text.length < 10) expect(commit).not.toHaveBeenCalled();
    expect(input).toHaveFocus();
  }
  expect(commit).toHaveBeenCalledExactlyOnceWith("2020-01-05");
  view.rerender(<PersonnelOrderDateFilter label="Дата с" value="2020-01-05" onCommit={commit} />);
  fireEvent.change(input, {target: {value: "05.01.202"}});
  expect(input).toHaveValue("05.01.202");
  expect(commit).toHaveBeenCalledTimes(1);
  fireEvent.change(input, {target: {value: "05.01.2021"}});
  expect(commit).toHaveBeenLastCalledWith("2021-01-05");
  expect(input).toHaveFocus();
});

it("does not apply impossible dates and supports valid leap days", () => {
  const commit = vi.fn();
  render(<PersonnelOrderDateFilter label="Дата по" onCommit={commit} />);
  fireEvent.change(screen.getByLabelText("Дата по"), {target: {value: "31.02.2020"}});
  fireEvent.blur(screen.getByLabelText("Дата по"));
  expect(screen.getByRole("alert")).toHaveTextContent("Введите корректную дату");
  expect(commit).not.toHaveBeenCalled();
  expect(parsePersonnelFilterDate("29.02.2020")).toBe("2020-02-29");
  expect(parsePersonnelFilterDate("29.02.2021")).toBeNull();
  expect(parsePersonnelFilterDate("05.01.0000")).toBeNull();
});

it("selects an old year directly in the calendar and clears the boundary", () => {
  const commit = vi.fn();
  const view = render(<PersonnelOrderDateFilter label="Дата с" value="2026-11-04" onCommit={commit} />);
  fireEvent.click(screen.getByRole("button", {name: "Открыть календарь: Дата с"}));
  fireEvent.change(screen.getByLabelText("Год: Дата с"), {target: {value: "2020"}});
  fireEvent.change(screen.getByLabelText("Месяц: Дата с"), {target: {value: "1"}});
  expect(commit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", {name: "05.01.2020"}));
  expect(screen.getByLabelText("Дата с")).toHaveValue("05.01.2020");
  expect(commit).toHaveBeenLastCalledWith("2020-01-05");
  expect(screen.getByLabelText("Дата с")).toHaveFocus();
  view.rerender(<PersonnelOrderDateFilter label="Дата с" value="2020-01-05" onCommit={commit} />);
  fireEvent.click(screen.getByRole("button", {name: "Очистить: Дата с"}));
  expect(screen.getByLabelText("Дата с")).toHaveValue("");
  expect(commit).toHaveBeenLastCalledWith(undefined);
});

it("resets incomplete input when all journal filters are reset", () => {
  const commit = vi.fn();
  const view = render(<PersonnelOrderDateFilter label="Дата с" onCommit={commit} resetKey={0} />);
  fireEvent.change(screen.getByLabelText("Дата с"), {target: {value: "05.01.20"}});
  view.rerender(<PersonnelOrderDateFilter label="Дата с" onCommit={commit} resetKey={1} />);
  expect(screen.getByLabelText("Дата с")).toHaveValue("");
  expect(commit).not.toHaveBeenCalled();
});
