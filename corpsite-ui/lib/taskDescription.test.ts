import { describe, expect, it } from "vitest";

import { splitTaskDescription, taskDescriptionForUser } from "./taskDescription";

const CATCH_UP_BLOCK = `
Источник: Догоняющий запуск регулярной задачи
ID запуска: 33
Дата возникновения задачи: 2026-06-11
Тип запуска: догоняющий
Период: Прошлая неделя`;

const AUTOMATIC_BLOCK = `
Источник: Автоматический запуск регулярной задачи
ID запуска: 10
Дата возникновения задачи: 2026-06-17
Тип запуска: автоматический`;

describe("splitTaskDescription", () => {
  it("splits human text from trailing origin metadata block", () => {
    const description = `Отчёт по амбулаторной экспертизе\n---${CATCH_UP_BLOCK}\n---`;
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("Отчёт по амбулаторной экспертизе");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.source).toContain("Догоняющий");
    expect(split.originMetadata.run_id).toBe("33");
    expect(split.originMetadata.run_kind).toBe("догоняющий");
    expect(split.originMetadata.period).toBe("Прошлая неделя");
  });

  it("handles metadata-only descriptions", () => {
    const description = `---${AUTOMATIC_BLOCK}\n---`;
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("10");
    expect(split.originMetadata.run_kind).toBe("автоматический");
  });

  it("returns full text when no origin metadata block is present", () => {
    const description = "Разовая задача без служебного блока";
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe(description);
    expect(split.hasOriginMetadata).toBe(false);
    expect(split.metadataBlock).toBeNull();
  });

  it("ignores trailing --- blocks without run id marker", () => {
    const description = "Текст задачи\n---\nПроизвольная пометка\n---";
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe(description);
    expect(split.hasOriginMetadata).toBe(false);
  });

  it("splits metadata when description uses CRLF line endings", () => {
    const description =
      "Отчёт по амбулаторной экспертизе\r\n---\r\nИсточник: Автоматический запуск регулярной задачи\r\nID запуска: 10\r\nТип запуска: автоматический\r\n---";
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("Отчёт по амбулаторной экспертизе");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("10");
  });
});

describe("taskDescriptionForUser", () => {
  it("strips scheduler metadata for regular users", () => {
    const description = `User-authored body\n---${AUTOMATIC_BLOCK}\n---`;
    expect(taskDescriptionForUser(description)).toBe("User-authored body");
  });
});
