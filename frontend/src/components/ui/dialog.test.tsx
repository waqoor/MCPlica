import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test } from "vitest";
import { Dialog } from "./dialog";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(true)} type="button">
        Open modal
      </button>
      <main>Background content</main>
      <Dialog
        description="Keyboard boundary"
        onClose={() => setOpen(false)}
        open={open}
        title="Test dialog"
      >
        <input aria-label="First field" />
        <button type="button">Last action</button>
      </Dialog>
    </div>
  );
}

test("traps focus, inerts the background, locks scrolling, and restores focus", async () => {
  const user = userEvent.setup();
  const rendered = render(<Harness />);
  const opener = screen.getByRole("button", { name: "Open modal" });
  await user.click(opener);

  const dialog = screen.getByRole("dialog", { name: "Test dialog" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(rendered.container).toHaveAttribute("inert");
  expect(rendered.container).toHaveAttribute("aria-hidden", "true");
  expect(document.body.style.overflow).toBe("hidden");
  expect(document.body.style.overscrollBehavior).toBe("contain");

  const close = screen.getByRole("button", { name: "Close dialog" });
  expect(close).toHaveFocus();
  await user.tab({ shift: true });
  expect(screen.getByRole("button", { name: "Last action" })).toHaveFocus();

  const last = screen.getByRole("button", { name: "Last action" });
  last.focus();
  await user.tab();
  expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
  expect(rendered.container).not.toHaveAttribute("inert");
  expect(rendered.container).not.toHaveAttribute("aria-hidden");
  expect(document.body.style.overflow).toBe("");
  expect(document.body.style.overscrollBehavior).toBe("");
});

function NestedHarness() {
  const [outer, setOuter] = useState(false);
  const [inner, setInner] = useState(false);
  return (
    <>
      <button onClick={() => setOuter(true)} type="button">
        Open outer
      </button>
      <Dialog onClose={() => setOuter(false)} open={outer} title="Outer dialog">
        <button onClick={() => setInner(true)} type="button">
          Open inner
        </button>
        <Dialog
          onClose={() => setInner(false)}
          open={inner}
          title="Inner dialog"
        >
          <button type="button">Inner action</button>
        </Dialog>
      </Dialog>
    </>
  );
}

test("keeps nested controls in the top modal and Escape closes one layer", async () => {
  const user = userEvent.setup();
  render(<NestedHarness />);
  await user.click(screen.getByRole("button", { name: "Open outer" }));
  await user.click(screen.getByRole("button", { name: "Open inner" }));
  expect(screen.getByRole("dialog", { name: "Inner dialog" })).toBeVisible();

  await user.keyboard("{Escape}");
  expect(
    screen.queryByRole("dialog", { name: "Inner dialog" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "Outer dialog" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Open inner" })).toHaveFocus();

  await user.keyboard("{Escape}");
  expect(
    screen.queryByRole("dialog", { name: "Outer dialog" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open outer" })).toHaveFocus();
});

test("uses the same named modal boundary for compact navigation sheets", async () => {
  const user = userEvent.setup();

  function SheetHarness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)} type="button">
          Open navigation
        </button>
        <Dialog
          description="Primary application navigation"
          onClose={() => setOpen(false)}
          open={open}
          title="Navigation"
          variant="sheet"
        >
          <nav aria-label="Primary">
            <a href="/projects">Projects</a>
          </nav>
        </Dialog>
      </>
    );
  }

  render(<SheetHarness />);
  const opener = screen.getByRole("button", { name: "Open navigation" });
  await user.click(opener);
  expect(screen.getByRole("dialog", { name: "Navigation" })).toHaveAttribute(
    "aria-describedby",
  );
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await user.keyboard("{Escape}");
  expect(opener).toHaveFocus();
});
