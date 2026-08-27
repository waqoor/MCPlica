import { describe, expect, it } from "vitest";
import { formatBytes } from "./format";

describe("formatBytes", () => {
  it("uses the runtime locale formatter for fractional units", () => {
    const localized = new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    }).format(1.5);

    expect(formatBytes(1_536)).toBe(`${localized} KB`);
  });

  it.each([null, undefined, -1, Number.NaN, Number.POSITIVE_INFINITY])(
    "fails safely for an invalid byte count (%s)",
    (value) => {
      expect(formatBytes(value)).toBe("Unknown size");
    },
  );
});
