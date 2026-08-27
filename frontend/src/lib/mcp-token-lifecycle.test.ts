import { describe, expect, test } from "vitest";
import { mcpTokenLifecycle, tokenExpirationToIso } from "./mcp-token-lifecycle";

const now = Date.parse("2026-08-27T12:00:00Z");

describe("MCP token lifecycle", () => {
  test.each([
    [{ revoked_at: null, expires_at: null }, "active"],
    [{ revoked_at: null, expires_at: "2026-08-27T12:00:01Z" }, "active"],
    [{ revoked_at: null, expires_at: "2026-08-27T12:00:00Z" }, "expired"],
    [
      {
        revoked_at: "2026-08-26T12:00:00Z",
        expires_at: "2026-08-28T12:00:00Z",
      },
      "revoked",
    ],
  ] as const)("derives %s as %s", (token, expected) => {
    expect(mcpTokenLifecycle(token, now)).toBe(expected);
  });

  test("converts local expiration input to an exact future ISO instant", () => {
    const expected = new Date("2026-08-28T09:30").toISOString();
    expect(tokenExpirationToIso("2026-08-28T09:30", now)).toEqual({
      value: expected,
      error: null,
    });
  });

  test("rejects expired or invalid expiration input", () => {
    expect(tokenExpirationToIso("2026-08-26T09:30", now).error).toMatch(
      /future/i,
    );
    expect(tokenExpirationToIso("not-a-date", now).error).toMatch(/valid/i);
    expect(tokenExpirationToIso("", now)).toEqual({ value: null, error: null });
  });
});
