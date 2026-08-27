async (page) => {
  const items = [
    {
      name: "Markdown document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.md",
    },
    {
      name: "Text document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.txt",
    },
    {
      name: "CSV document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.csv",
    },
    {
      name: "XLSX document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.xlsx",
    },
    {
      name: "DOCX document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.docx",
    },
    {
      name: "PDF document upload",
      path: "E:\\ABC\\MCPlica\\output\\playwright\\upload-review\\sample.pdf",
    },
  ];
  const results = [];

  for (const [index, item] of items.entries()) {
    if (index > 0) {
      await page
        .getByRole("button", { name: "Add source", exact: true })
        .first()
        .evaluate((element) => element.click());
    }
    const dialog = page.getByRole("dialog");
    await dialog.waitFor({ state: "visible" });
    await dialog.getByLabel("Name").fill(item.name);
    await dialog.getByLabel("Kind").selectOption({ label: "Documentation" });
    await dialog.locator("input[type=file]").setInputFiles(item.path);
    await dialog
      .getByRole("button", { name: "Add source", exact: true })
      .evaluate((element) => element.click());
    await page
      .getByRole("heading", { name: item.name, exact: true })
      .waitFor({ state: "visible", timeout: 20_000 });
    results.push(item.name);
  }

  return results;
}
