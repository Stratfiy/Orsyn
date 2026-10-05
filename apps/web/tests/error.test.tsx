import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ErrorPage from "@/app/error";

describe("ErrorPage", () => {
  it("renders with role alert", () => {
    const mockReset = vi.fn();
    const error = new Error("Test error");

    render(<ErrorPage error={error} reset={mockReset} />);

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
  });

  it("renders h1 with text Something went wrong", () => {
    const mockReset = vi.fn();
    const error = new Error("Test error");

    render(<ErrorPage error={error} reset={mockReset} />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Something went wrong");
  });

  it("renders button with text Try again", () => {
    const mockReset = vi.fn();
    const error = new Error("Test error");

    render(<ErrorPage error={error} reset={mockReset} />);

    const button = screen.getByRole("button", { name: "Try again" });
    expect(button).toBeInTheDocument();
  });

  it("calls reset once when button is clicked", async () => {
    const user = userEvent.setup();
    const mockReset = vi.fn();
    const error = new Error("Test error");

    render(<ErrorPage error={error} reset={mockReset} />);

    const button = screen.getByRole("button", { name: "Try again" });
    await user.click(button);

    expect(mockReset).toHaveBeenCalledOnce();
  });
});
