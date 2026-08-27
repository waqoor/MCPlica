import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { ApiError } from "@/api/client";
import { ErrorNotice } from "./error-notice";

afterEach(() => vi.restoreAllMocks());

test("renders stable operator evidence, redacts sensitive details, and copies request id", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  render(
    <ErrorNotice
      error={
        new ApiError(
          409,
          "A build is already active.",
          "BUILD_ACTIVE",
          {
            operation_keys: ["listPets", "getPet"],
            token: "must-not-render",
            stack_trace: "must-not-render",
          },
          "request-operator-123",
        )
      }
    />,
  );

  expect(screen.getByText("BUILD_ACTIVE")).toBeVisible();
  expect(screen.getByText("request-operator-123")).toBeVisible();
  expect(screen.getByText("listPets, getPet")).toBeVisible();
  expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: "Copy request ID" }),
  );
  expect(writeText).toHaveBeenCalledWith("request-operator-123");
  expect(await screen.findByText("Request ID copied.")).toBeVisible();
});

test("announces clipboard failure without hiding the selectable request id", async () => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
  });
  render(
    <ErrorNotice
      error={
        new ApiError(500, "Safe failure", "SAFE_FAILURE", {}, "request-456")
      }
    />,
  );

  await userEvent.click(
    screen.getByRole("button", { name: "Copy request ID" }),
  );
  expect(
    await screen.findByText(
      "Could not copy the request ID. Select it manually.",
    ),
  ).toBeVisible();
  expect(screen.getByText("request-456")).toBeVisible();
});
