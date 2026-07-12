import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AccessDeniedPanel from "./AccessDeniedPanel";

afterEach(() => cleanup());

describe("AccessDeniedPanel", () => {
  it("shows user-friendly access explanation", () => {
    render(
      <AccessDeniedPanel
        me={{
          has_personnel_admin: true,
          has_operational_orders_read: false,
        }}
      />,
    );

    expect(screen.getByTestId("oo-access-denied")).toBeTruthy();
    expect(screen.getByText(/OPERATIONAL_ORDERS_INTAKE_READ/)).toBeTruthy();
    expect(screen.getByText(/Personnel Orders/)).toBeTruthy();
  });

  it("shows developer diagnostics only in development", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<AccessDeniedPanel me={{ has_operational_orders_read: false }} />);
    expect(screen.getByTestId("oo-access-diagnostics")).toBeTruthy();
    vi.unstubAllEnvs();
  });
});
