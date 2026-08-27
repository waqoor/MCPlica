async (page) => {
  await page.locator("main").waitFor();
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      [...document.images].map((image) =>
        image.complete ? image.decode().catch(() => undefined) : undefined,
      ),
    );
  });

  return page.evaluate(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    };
    const smallControls = [...document.querySelectorAll("button")]
      .filter(visible)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          name:
            element.getAttribute("aria-label") ||
            element.textContent?.trim() ||
            "button",
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      })
      .filter(({ width, height }) => width < 44 || height < 44);

    const rootOverflowX = getComputedStyle(document.documentElement).overflowX;
    const horizontalOverflow =
      document.documentElement.scrollWidth >
        document.documentElement.clientWidth &&
      rootOverflowX !== "clip" &&
      rootOverflowX !== "hidden";

    return {
      url: location.pathname,
      viewport: {
        width: document.documentElement.clientWidth,
        height: document.documentElement.clientHeight,
      },
      colorScheme: matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light",
      horizontalOverflow,
      failedImages: [...document.images]
        .filter((image) => !image.complete || image.naturalWidth === 0)
        .map((image) => image.currentSrc),
      logos: [...document.querySelectorAll(".brand-logo")]
        .filter(visible)
        .map((element) => {
          const image = element.querySelector("img");
          const rect = element.getBoundingClientRect();
          return {
            variant: element.classList.contains("brand-logo--compact")
              ? "compact"
              : "primary",
            rendered: `${Math.round(rect.width)}x${Math.round(rect.height)}`,
            natural: image
              ? `${image.naturalWidth}x${image.naturalHeight}`
              : "missing",
          };
        }),
      smallControls,
    };
  });
}
