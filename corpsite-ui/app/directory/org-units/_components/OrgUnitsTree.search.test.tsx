import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import OrgUnitsTree, {
  filterTreeForSearch,
  nodeMatchesQuery,
  type TreeNode,
} from "./OrgUnitsTree";

const sampleNodes: TreeNode[] = [
  {
    id: "10",
    title: "Многопрофильный медицинский центр",
    code: "MMC",
    type: "unit",
    children: [
      {
        id: "101",
        title: "Терапевтическое отделение",
        code: "THER",
        type: "unit",
        children: [
          {
            id: "1011",
            title: "Процедурный кабинет",
            code: "PROC",
            type: "unit",
            children: [],
          },
        ],
      },
      {
        id: "202",
        title: "Отдел кадров",
        code: "HR",
        type: "unit",
        children: [],
      },
    ],
  },
];

describe("OrgUnitsTree search helpers", () => {
  it("matches by title case-insensitively", () => {
    const re = /кадр/i;
    expect(nodeMatchesQuery({ id: "202", title: "Отдел кадров", code: "HR" }, re)).toBe(true);
  });

  it("matches by code", () => {
    const re = /ther/i;
    expect(nodeMatchesQuery({ id: "101", title: "Терапевтическое отделение", code: "THER" }, re)).toBe(true);
  });

  it("matches by id", () => {
    const re = /1011/;
    expect(nodeMatchesQuery({ id: "1011", title: "Процедурный кабинет", code: "PROC" }, re)).toBe(true);
  });

  it("filters tree and keeps ancestors of matches", () => {
    const { nodes, matchIds } = filterTreeForSearch({
      nodes: sampleNodes,
      q: "PROC",
      inactiveSet: new Set(),
      showInactive: false,
    });
    expect(matchIds.has("1011")).toBe(true);
    expect(nodes[0].children?.some((c) => c.id === "101")).toBe(true);
    const dept = nodes[0].children?.find((c) => c.id === "101");
    expect(dept?.children?.some((c) => c.id === "1011")).toBe(true);
  });

  it("returns full tree when query is empty", () => {
    const { nodes, matchIds } = filterTreeForSearch({
      nodes: sampleNodes,
      q: "",
      inactiveSet: new Set(),
      showInactive: false,
    });
    expect(matchIds.size).toBe(0);
    expect(nodes).toHaveLength(1);
  });
});

describe("OrgUnitsTree search UI", () => {
  afterEach(() => cleanup());

  it("highlights and auto-selects a single search result", async () => {
    const onSelect = vi.fn();
    const onSearch = vi.fn();
    const onToggle = vi.fn();

    render(
      <OrgUnitsTree
        nodes={sampleNodes}
        expandedIds={["10", "101"]}
        selectedId={null}
        inactiveIds={[]}
        searchQuery="PROC"
        can={{ add: false, rename: false, move: false, deactivate: false }}
        onSelect={onSelect}
        onToggle={onToggle}
        onAction={vi.fn()}
        onSearch={onSearch}
        onResetExpand={vi.fn()}
      />,
    );

    expect(screen.getByText(/Процедурный кабинет/)).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith("1011"));
  });

  it("clears search and restores tree", () => {
    const onSearch = vi.fn();

    const { rerender } = render(
      <OrgUnitsTree
        nodes={sampleNodes}
        expandedIds={["10", "101"]}
        selectedId="1011"
        inactiveIds={[]}
        searchQuery="PROC"
        can={{ add: false, rename: false, move: false, deactivate: false }}
        onSelect={vi.fn()}
        onToggle={vi.fn()}
        onAction={vi.fn()}
        onSearch={onSearch}
        onResetExpand={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByLabelText("Очистить поиск"));
    expect(onSearch).toHaveBeenCalledWith("");

    rerender(
      <OrgUnitsTree
        nodes={sampleNodes}
        expandedIds={["10", "101"]}
        selectedId="1011"
        inactiveIds={[]}
        searchQuery=""
        can={{ add: false, rename: false, move: false, deactivate: false }}
        onSelect={vi.fn()}
        onToggle={vi.fn()}
        onAction={vi.fn()}
        onSearch={onSearch}
        onResetExpand={vi.fn()}
      />,
    );

    expect(screen.getByText("Отдел кадров")).toBeInTheDocument();
  });
});
