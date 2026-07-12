import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import WorkspaceStageBadge from "./WorkspaceStageBadge";

afterEach(() => cleanup());

describe("WorkspaceStageBadge", () => {
  it("shows Russian stage label", () => {
    render(<WorkspaceStageBadge stage="EDITORIAL_PACKAGE_READY" />);
    expect(screen.getByText("Редакционный пакет готов")).toBeTruthy();
  });
});
