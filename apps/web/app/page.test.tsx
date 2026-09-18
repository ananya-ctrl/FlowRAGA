import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("home page", () => {
  it("states the product purpose", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Build retrieval systems you can actually understand.",
    );
    expect(screen.getByRole("link", { name: "View repository" })).toHaveAttribute(
      "href",
      "https://github.com/ananya-ctrl/FlowRAGA",
    );
  });
});

