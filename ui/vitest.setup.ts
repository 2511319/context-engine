import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";
import React from "react";

vi.mock("recharts", () => {
  const MockContainer = ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children);
  const MockLeaf = () => null;
  return {
    ResponsiveContainer: MockContainer,
    BarChart: MockContainer,
    PieChart: MockContainer,
    Bar: MockContainer,
    Pie: MockContainer,
    Cell: MockLeaf,
    XAxis: MockLeaf,
    YAxis: MockLeaf,
    Tooltip: MockLeaf,
    // Alias used in ExplainPage
    RechartsTooltip: MockLeaf,
  };
});
