import { describe, expect, it } from "vitest";

import { splitTaskDescription, taskDescriptionForUser } from "./taskDescription";

const CATCH_UP_BLOCK_41 = `
Источник: Догоняющий запуск регулярной задачи
ID запуска: 41
Дата возникновения задачи: 2026-06-11
Тип запуска: догоняющий
Период: Прошлая неделя`;

const CATCH_UP_BLOCK_43 = `
Источник: Догоняющий запуск регулярной задачи
ID запуска: 43
Дата возникновения задачи: 2026-06-17
Тип запуска: догоняющий
Период: Прошлая неделя`;

const AUTOMATIC_BLOCK = `
Источник: Автоматический запуск регулярной задачи
ID запуска: 10
Дата возникновения задачи: 2026-06-17
Тип запуска: автоматический`;

/** Dedup scenario: backend appends a second run block to metadata-only description. */
const DOUBLE_METADATA_ONLY = `---${CATCH_UP_BLOCK_41}
---
---${CATCH_UP_BLOCK_43}
---`;

const HUMAN_TEXT = "Отчет по госпитальной экспертизе за период";

/** Live production shape for task_id=10018 (double catch-up metadata-only). */
const TASK_10018_DESCRIPTION = `---
Источник: Догоняющий запуск регулярной задачи
ID запуска: 41
Дата возникновения задачи: 2026-06-24
Тип запуска: догоняющий
Период: Ручная дата
---
---
Источник: Догоняющий запуск регулярной задачи
ID запуска: 43
Дата возникновения задачи: 2026-06-24
Тип запуска: догоняющий
Период: Ручная дата
---`;

describe("splitTaskDescription", () => {
  it("splits human text from a single trailing origin metadata block", () => {
    const description = `Отчёт по амбулаторной экспертизе\n---${CATCH_UP_BLOCK_41.replace("41", "33")}\n---`;
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("Отчёт по амбулаторной экспертизе");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("33");
  });

  it("handles a single metadata-only description", () => {
    const description = `---${AUTOMATIC_BLOCK}\n---`;
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("10");
  });

  it("strips double metadata blocks (dedup append, metadata-only)", () => {
    const split = splitTaskDescription(DOUBLE_METADATA_ONLY);

    expect(split.humanText).toBe("");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("43");
    expect(taskDescriptionForUser(DOUBLE_METADATA_ONLY)).toBe("");
  });

  it("strips double metadata blocks after human text", () => {
    const description = `${HUMAN_TEXT}\n---${CATCH_UP_BLOCK_41}\n---\n---${CATCH_UP_BLOCK_43}\n---`;
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe(HUMAN_TEXT);
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("43");
    expect(taskDescriptionForUser(description)).toBe(HUMAN_TEXT);
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

  it("task_id=10018-like double catch-up blocks leave no visible metadata for non-admin", () => {
    const split = splitTaskDescription(TASK_10018_DESCRIPTION);

    expect(split.humanText).toBe("");
    expect(split.hasOriginMetadata).toBe(true);
    expect(split.originMetadata.run_id).toBe("43");
    expect(taskDescriptionForUser(TASK_10018_DESCRIPTION)).toBe("");
    expect(taskDescriptionForUser(TASK_10018_DESCRIPTION)).not.toContain("ID запуска:");
    expect(taskDescriptionForUser(TASK_10018_DESCRIPTION)).not.toContain("Догоняющий");
  });

  it("task_id=10018-like CRLF metadata-only double block yields empty humanText", () => {
    const description = TASK_10018_DESCRIPTION.replace(/\n/g, "\r\n");
    const split = splitTaskDescription(description);

    expect(split.humanText).toBe("");
    expect(split.hasOriginMetadata).toBe(true);
  });
});

describe("taskDescriptionForUser", () => {
  it("strips scheduler metadata for regular users", () => {
    const description = `User-authored body\n---${AUTOMATIC_BLOCK}\n---`;
    expect(taskDescriptionForUser(description)).toBe("User-authored body");
  });
});
