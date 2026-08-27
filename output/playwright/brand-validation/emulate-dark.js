async (page) => {
  await page.emulateMedia({
    colorScheme: "dark",
    reducedMotion: "no-preference",
  });
  await page.reload();
  await page.evaluate(() => document.fonts.ready);
  return page.evaluate(() => ({
    colorScheme: matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light",
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
