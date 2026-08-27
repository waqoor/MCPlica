import { describe, expect, it } from "vitest";
import { MAX_UPLOAD_BYTES, uploadFileError } from "./uploads";

function file(name: string, size: number): File {
  const result = new File(["x"], name);
  Object.defineProperty(result, "size", { value: size });
  return result;
}

describe("upload file validation", () => {
  it.each(["json", "md", "txt", "csv", "xlsx", "docx", "pdf"])(
    "accepts .%s documentation",
    (extension) => {
      expect(
        uploadFileError(file(`source.${extension}`, 1), "documentation"),
      ).toBeNull();
    },
  );

  it("accepts the exact 100 MB boundary and rejects one byte above it", () => {
    expect(
      uploadFileError(file("source.txt", MAX_UPLOAD_BYTES), "documentation"),
    ).toBeNull();
    expect(
      uploadFileError(
        file("source.txt", MAX_UPLOAD_BYTES + 1),
        "documentation",
      ),
    ).toMatch(/100 MB/);
  });

  it("keeps executable uploads constrained to JSON or YAML", () => {
    expect(uploadFileError(file("openapi.json", 1), "openapi")).toBeNull();
    expect(uploadFileError(file("notes.pdf", 1), "openapi")).toMatch(
      /JSON or YAML/,
    );
  });
});
