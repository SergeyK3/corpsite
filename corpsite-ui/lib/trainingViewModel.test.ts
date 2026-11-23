import { describe, expect, it } from "vitest";
import { groupTrainingResults, trainingAction, trainingLessonTitle, trainingStatus } from "./trainingViewModel";
import type { TrainingSummaryItem } from "./trainingApi";

describe("training presentation", () => {
  it.each([
    [null, null, "Не начато", "Подготовить и начать"],
    ["in_progress", null, "В работе", "Продолжить"],
    ["under_review", null, "На проверке", "Посмотреть отправленную работу"],
    ["completed", "passed", "Зачтено", "Посмотреть результат"],
    ["completed", "failed", "Не зачтено", "Посмотреть результат"],
  ])("maps %s/%s to the assigned action", (state, outcome, label, action) => {
    expect(trainingStatus(state, outcome)).toBe(label);
    expect(trainingAction(state)).toBe(action);
  });

  it("puts the latest assigned course version before older under-review work", () => {
    const item = (assignment_id: number, course_version: number): TrainingSummaryItem => ({
      assignment_id, course_code: "admin_hire", course_title: "Курс",
      course_version, lesson_code: "skill_2", lesson_number: 2, lesson_title: "Занятие", attempts: [],
    });
    const [group] = groupTrainingResults([item(23, 2), item(34, 3)]);
    expect(group.current.assignment_id).toBe(34);
    expect(group.history.map((old) => old.assignment_id)).toEqual([23]);
  });

  it("formats the catalog number separately from attempt and application numbers", () => {
    expect(trainingLessonTitle(2, "Одобрить заявление о приёме на работу"))
      .toBe("Занятие №2. Одобрить заявление о приёме на работу");
  });
});
