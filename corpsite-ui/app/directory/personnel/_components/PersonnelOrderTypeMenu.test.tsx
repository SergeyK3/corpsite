import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PersonnelOrderTypeMenu, { orderTypeMenuHorizontalPosition, pointerHeadsToSubmenu } from "./PersonnelOrderTypeMenu";
import { personnelOrderTypeLabel } from "../_lib/personnelOrderLabels";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const open = () => fireEvent.click(screen.getByRole("button", { name: "Тип кадрового приказа" }));

it.each(["ru", "kk"] as const)("opens seven %s groups and selects an existing code by group click", language => {
  const choose = vi.fn();
  render(<PersonnelOrderTypeMenu value="" language={language} onChange={choose} />);
  open();
  const menu = screen.getByRole("menu", { name: language === "ru" ? "Группы приказов" : "Бұйрық топтары" });
  expect(within(menu).getAllByRole("menuitem")).toHaveLength(7);
  fireEvent.click(screen.getByRole("menuitem", { name: language === "ru" ? "Отпуск без содержания" : "Жалақы сақталмайтын демалыс" }));
  expect(choose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("menuitem", { name: personnelOrderTypeLabel("LEAVE.UNPAID.GRANT", language) }));
  expect(choose).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT");
  expect(screen.queryByTestId("personnel-order-type-menu")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toHaveFocus();
});

it("keeps the submenu open across neighbouring rows on the way to its items", () => {
  vi.useFakeTimers();
  vi.stubGlobal("PointerEvent", MouseEvent);
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={() => {}} />);
  open();
  fireEvent.pointerEnter(screen.getByRole("menuitem", { name: "Трудовой отпуск" }), { clientX: 240, clientY: 210 });
  expect(screen.getByRole("menuitem", { name: personnelOrderTypeLabel("LEAVE.ANNUAL.GRANT", "ru") })).toBeInTheDocument();
  const submenu = screen.getByRole("menu", { name: "Трудовой отпуск" });
  vi.spyOn(submenu, "getBoundingClientRect").mockReturnValue({ left: 280, right: 640, top: 80, bottom: 450 } as DOMRect);
  fireEvent.pointerEnter(screen.getByRole("menuitem", { name: "Беременность, роды и уход за ребёнком" }), { clientX: 250, clientY: 190 });
  fireEvent.pointerEnter(screen.getByRole("menu", { name: "Трудовой отпуск" }), { pointerType: "mouse" });
  act(() => vi.advanceTimersByTime(300));
  expect(screen.getByRole("menuitem", { name: personnelOrderTypeLabel("LEAVE.ANNUAL.GRANT", "ru") })).toBeInTheDocument();
});

it("recognizes travel toward both left and right submenus and rejects movement away", () => {
  const bounds = { left: 280, right: 640, top: 80, bottom: 450 };
  expect(pointerHeadsToSubmenu({ x: 240, y: 210 }, { x: 260, y: 170 }, bounds, "right")).toBe(true);
  expect(pointerHeadsToSubmenu({ x: 240, y: 210 }, { x: 220, y: 170 }, bounds, "right")).toBe(false);
  expect(pointerHeadsToSubmenu({ x: 680, y: 210 }, { x: 660, y: 170 }, bounds, "left")).toBe(true);
});

it("shows empty groups without inventing selectable order types", () => {
  const choose = vi.fn();
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={choose} />);
  open();
  fireEvent.click(screen.getByRole("menuitem", { name: "Другие отпуска" }));
  expect(screen.getByRole("status")).toHaveTextContent("Пока нет доступных видов");
  expect(choose).not.toHaveBeenCalled();
});

it.each([
  ["kk", "трудов", personnelOrderTypeLabel("LEAVE.ANNUAL.GRANT", "kk"), "LEAVE.ANNUAL.GRANT"],
  ["ru", "жұмысқа қабылдау", "О приёме на работу", "HIRE"],
] as const)("searches the other language in %s and chooses the result directly", (language, query, name, code) => {
  const choose = vi.fn();
  render(<PersonnelOrderTypeMenu value="" language={language} onChange={choose} />);
  open();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: query } });
  expect(screen.getAllByRole("menuitem")).toHaveLength(1);
  fireEvent.click(screen.getByRole("menuitem", { name }));
  expect(choose).toHaveBeenCalledWith(code);
});

it("navigates from search to groups and submenu, back with arrows, and restores focus on Escape", async () => {
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={() => {}} />);
  open();
  expect(screen.getByRole("searchbox")).toHaveFocus();
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "ArrowDown" });
  const group = screen.getByRole("menuitem", { name: "Трудовой отпуск" });
  expect(group).toHaveFocus();
  fireEvent.keyDown(group, { key: "ArrowRight" });
  const type = screen.getByRole("menuitem", { name: personnelOrderTypeLabel("LEAVE.ANNUAL.GRANT", "ru") });
  await waitFor(() => expect(type).toHaveFocus());
  fireEvent.keyDown(type, { key: "ArrowLeft" });
  expect(group).toHaveFocus();
  fireEvent.keyDown(group, { key: "Escape" });
  expect(screen.queryByTestId("personnel-order-type-menu")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toHaveFocus();
});

it("selects a search result with Enter without submitting a form", () => {
  const choose = vi.fn();
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={choose} />);
  open();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "увольнении" } });
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Enter" });
  expect(choose).toHaveBeenCalledWith("TERMINATION");
});

it("closes on an outside click and clears the old search when reopened", () => {
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={() => {}} />);
  open();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "nothing" } });
  expect(screen.getByRole("status")).toHaveTextContent("Ничего не найдено");
  fireEvent.pointerDown(document.body);
  expect(screen.queryByTestId("personnel-order-type-menu")).not.toBeInTheDocument();
  open();
  expect(screen.getByRole("searchbox")).toHaveValue("");
});

it("changes only the display label when the shared language changes", () => {
  const choose = vi.fn();
  const view = render(<PersonnelOrderTypeMenu value="HIRE" language="ru" onChange={choose} />);
  expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toHaveTextContent("О приёме на работу");
  view.rerender(<PersonnelOrderTypeMenu value="HIRE" language="kk" onChange={choose} />);
  expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toHaveTextContent("Жұмысқа қабылдау туралы");
  expect(choose).not.toHaveBeenCalled();
});

it("fits to the right, flips left at the edge and stacks on a narrow touchscreen", () => {
  expect(orderTypeMenuHorizontalPosition(100, 1200).side).toBe("right");
  const flipped = orderTypeMenuHorizontalPosition(800, 1000);
  expect(flipped.side).toBe("left");
  expect(flipped.left).toBeGreaterThanOrEqual(8);
  expect(flipped.left + flipped.groupWidth + flipped.itemWidth).toBeLessThanOrEqual(992);
  const narrow = orderTypeMenuHorizontalPosition(30, 390);
  expect(narrow.side).toBe("below");
  expect(narrow.left + narrow.groupWidth).toBeLessThanOrEqual(382);
});

it("uses the visible touch viewport and keeps the frame fixed during its own scrolling", () => {
  vi.stubGlobal("visualViewport", { width: 390, height: 844, offsetLeft: 0, offsetTop: 0, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  render(<PersonnelOrderTypeMenu value="" language="ru" onChange={() => {}} />);
  const trigger = screen.getByRole("button", { name: "Тип кадрового приказа" });
  vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({ left: 30, right: 330, top: 400, bottom: 440, width: 300, height: 40 } as DOMRect);
  open();
  const popup = screen.getByTestId("personnel-order-type-menu");
  expect(popup).toHaveStyle({ top: "444px", maxHeight: "392px" });
  fireEvent.click(screen.getByRole("menuitem", { name: "Приём, увольнение, назначение, перевод" }));
  fireEvent.scroll(popup);
  expect(popup).toHaveStyle({ top: "444px", maxHeight: "392px" });
});
