async (page) => {
  const projectId = "845d3c75-ca77-4026-ab2b-dc04260b741b";
  const buildId = "7f8f3088-eabd-4f32-b524-dad95a2ad5aa";
  const routes = [
    "/",
    "/projects",
    "/projects/new",
    `/projects/${projectId}`,
    `/projects/${projectId}/sources`,
    `/projects/${projectId}/tools`,
    `/projects/${projectId}/documentation`,
    `/projects/${projectId}/builds`,
    `/projects/${projectId}/builds/${buildId}`,
    `/projects/${projectId}/validation/${buildId}`,
    `/projects/${projectId}/deployment`,
    `/projects/${projectId}/credentials`,
    `/projects/${projectId}/settings`,
    "/builds",
    "/deployments",
    "/activity",
    "/settings",
    "/settings/models",
    "/settings/users",
    "/brand-validation-not-found",
  ];
  const passes = [
    { name: "dark-desktop", width: 1440, height: 1000, colorScheme: "dark" },
    { name: "light-mobile", width: 375, height: 812, colorScheme: "light" },
  ];
  const origin = "http://127.0.0.1:5173";
  const results = {};

  for (const pass of passes) {
    await page.setViewportSize({ width: pass.width, height: pass.height });
    await page.emulateMedia({ colorScheme: pass.colorScheme });
    const failures = {
      horizontalOverflow: [],
      failedImages: [],
      missingMain: [],
      missingLogo: [],
      headingCount: [],
      unnamedButtons: [],
      smallButtons: [],
      tokenMismatch: [],
    };

    for (const route of routes) {
      await page.goto(`${origin}${route}`, { waitUntil: "domcontentloaded" });
      await page.locator("main").waitFor({ timeout: 10_000 });
      await page.locator("h1").waitFor({ timeout: 10_000 });
      await page.waitForTimeout(80);
      const audit = await page.evaluate(() => {
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
        const visibleButtons = [...document.querySelectorAll("button")].filter(
          visible,
        );
        const rootOverflowX = getComputedStyle(
          document.documentElement,
        ).overflowX;
        const horizontalOverflow =
          document.documentElement.scrollWidth >
            document.documentElement.clientWidth &&
          rootOverflowX !== "clip" &&
          rootOverflowX !== "hidden";

        return {
          canvas: getComputedStyle(document.documentElement)
            .getPropertyValue("--color-canvas")
            .trim(),
          failedImages: [...document.images]
            .filter((image) => !image.complete || image.naturalWidth === 0)
            .map((image) => image.currentSrc),
          hasMain: Boolean(document.querySelector("main")),
          headingCount: document.querySelectorAll("h1").length,
          horizontalOverflow,
          visibleLogos: [...document.querySelectorAll(".brand-logo")].filter(
            visible,
          ).length,
          unnamedButtons: visibleButtons
            .filter(
              (button) =>
                !button.getAttribute("aria-label") &&
                !button.textContent?.trim(),
            )
            .length,
          smallButtons: visibleButtons
            .map((button) => button.getBoundingClientRect())
            .filter((rect) => rect.width < 44 || rect.height < 44).length,
        };
      });

      if (audit.horizontalOverflow) failures.horizontalOverflow.push(route);
      if (audit.failedImages.length) failures.failedImages.push(route);
      if (!audit.hasMain) failures.missingMain.push(route);
      if (!audit.visibleLogos) failures.missingLogo.push(route);
      if (audit.headingCount !== 1)
        failures.headingCount.push(`${route}:${audit.headingCount}`);
      if (audit.unnamedButtons) failures.unnamedButtons.push(route);
      if (audit.smallButtons) failures.smallButtons.push(route);
      const expectedCanvas =
        pass.colorScheme === "dark" ? "#050a20" : "#f5f7ff";
      if (audit.canvas !== expectedCanvas) failures.tokenMismatch.push(route);
    }

    results[pass.name] = {
      routesChecked: routes.length,
      failures,
    };
  }

  return results;
}
