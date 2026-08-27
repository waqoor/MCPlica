import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import { OneTimeSecretDialog } from "./one-time-secret-dialog";

const originalClipboard = Object.getOwnPropertyDescriptor(
  Navigator.prototype,
  "clipboard",
);

afterEach(() => {
  vi.restoreAllMocks();
  if (originalClipboard)
    Object.defineProperty(Navigator.prototype, "clipboard", originalClipboard);
  else delete (Navigator.prototype as { clipboard?: Clipboard }).clipboard;
});

function clipboard(writeText: (value: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
}

describe("OneTimeSecretDialog", () => {
  test("guards navigation and closing until storage is acknowledged", async () => {
    const user = userEvent.setup();
    const acknowledged = vi.fn();
    render(
      <OneTimeSecretDialog
        onAcknowledged={acknowledged}
        secret="mcp_once_secret"
      />,
    );

    const navigation = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(navigation);
    expect(navigation.defaultPrevented).toBe(true);

    await user.click(
      screen.getAllByRole("button", { name: "Close dialog" })[0]!,
    );
    expect(acknowledged).not.toHaveBeenCalled();
    expect(screen.getByText(/confirm that the token is stored/i)).toBeVisible();

    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getByRole("button", { name: "Finish and hide token" }),
    );
    expect(acknowledged).toHaveBeenCalledOnce();
  });

  test("announces clipboard success without exposing it outside the dialog", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    clipboard(writeText);
    render(
      <OneTimeSecretDialog onAcknowledged={() => undefined} secret="secret" />,
    );

    await user.click(screen.getByRole("button", { name: "Copy access token" }));

    expect(writeText).toHaveBeenCalledWith("secret");
    expect(screen.getByText(/token copied to the clipboard/i)).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  test("announces clipboard failure and keeps acknowledgement explicit", async () => {
    const user = userEvent.setup();
    clipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(
      <OneTimeSecretDialog onAcknowledged={() => undefined} secret="secret" />,
    );

    await user.click(screen.getByRole("button", { name: "Copy access token" }));

    await waitFor(() =>
      expect(screen.getByText(/copy failed/i)).toHaveAttribute(
        "aria-live",
        "polite",
      ),
    );
    expect(
      screen.getByRole("button", { name: "Finish and hide token" }),
    ).toBeDisabled();
  });
});
