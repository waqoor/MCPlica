async (page) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto("http://127.0.0.1:5173/", {
    waitUntil: "domcontentloaded",
  });
  await page.locator("h1").waitFor();
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.keyboard.press("Tab");

  return page.evaluate(() => {
    const button = document.querySelector("button");
    const buttonStyle = button ? getComputedStyle(button) : null;
    const active = document.activeElement;
    const activeStyle =
      active instanceof HTMLElement ? getComputedStyle(active) : null;
    return {
      reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      buttonTransitionDuration: buttonStyle?.transitionDuration,
      focusedElement:
        active?.getAttribute("aria-label") || active?.textContent?.trim(),
      focusOutlineWidth: activeStyle?.outlineWidth,
      focusTransform: activeStyle?.transform,
    };
  });
}
