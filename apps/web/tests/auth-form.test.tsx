import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { AuthForm } from "@/components/auth-form";

describe("AuthForm", () => {
  it("shows immediate progress and prevents duplicate submissions", () => {
    render(
      <AuthForm action="/auth/login" idleLabel="Sign in" pendingLabel="Signing in..." tone="dark">
        <input name="email" />
      </AuthForm>
    );

    const form = screen.getByRole("button", { name: "Sign in" }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    const button = screen.getByRole("button", { name: "Signing in..." });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("first request after inactivity");
  });
});
