async (page) => {
  await page.emulateMedia({
    colorScheme: "light",
    reducedMotion: "no-preference",
  });
  await page.reload();
  await page.evaluate(() => document.fonts.ready);
  return page.evaluate(() => ({
    colorScheme: matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark",
    canvas: getComputedStyle(document.documentElement)
      .getPropertyValue("--color-canvas")
      .trim(),
    horizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    images: [...document.images].map((image) => ({
      alt: image.alt,
      complete: image.complete,
      naturalWidth: image.naturalWidth,
    })),
  }));
}
