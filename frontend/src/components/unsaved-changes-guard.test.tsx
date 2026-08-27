import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, createMemoryRouter, RouterProvider } from "react-router-dom";
import { expect, test } from "vitest";
import { UnsavedChangesGuard } from "./unsaved-changes-guard";

function DirtyPage() {
  return (
    <>
      <UnsavedChangesGuard active />
      <h1>Dirty settings</h1>
      <Link to="/next">Leave settings</Link>
    </>
  );
}

test("blocks internal navigation until unsaved changes are explicitly discarded", async () => {
  const router = createMemoryRouter(
    [
      { path: "/", element: <DirtyPage /> },
      { path: "/next", element: <h1>Next page</h1> },
    ],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);

  await userEvent.click(screen.getByRole("link", { name: "Leave settings" }));
  expect(
    screen.getByRole("dialog", { name: "Discard unsaved changes?" }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));
  expect(screen.getByRole("heading", { name: "Dirty settings" })).toBeVisible();

  await userEvent.click(screen.getByRole("link", { name: "Leave settings" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Discard and leave" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Next page" }),
  ).toBeVisible();
});
