async (page) => {
  await page.locator("main").waitFor();
  return page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const items = [...document.querySelectorAll("html, body, #root, body *")]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return {
          tag: element.tagName.toLowerCase(),
          classes: element.className?.toString().slice(0, 180) || "",
          text: element.textContent?.trim().replace(/\s+/g, " ").slice(0, 80),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
          overflowX: style.overflowX,
        };
      });
    return {
      outsideViewport: items
        .filter(
          (item) =>
            item.width > 0 &&
            (item.left < -1 || item.right > viewportWidth + 1),
        )
        .slice(0, 30),
      scrollContainers: items
        .filter(
          (item) =>
            item.clientWidth > 0 && item.scrollWidth > item.clientWidth + 1,
        )
        .slice(0, 30),
    };
  });
}
