import { afterEach, expect, it, vi } from "vitest";
import { BUILD_STATUSES } from "./generated/constants";
import { buildApi, parseBuildStatusFilter } from "./builds";

afterEach(() => {
  vi.restoreAllMocks();
});

const emptyBuildPage = {
  items: [],
  total: 0,
  page: 1,
  page_size: 50,
  has_active: false,
};

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

it.each(BUILD_STATUSES)(
  "sends the generated %s Build status wire value",
  async (status) => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(emptyBuildPage));

    await expect(buildApi.listAll({ status })).resolves.toEqual([]);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `/api/v1/builds?status=${status}`,
    );
  },
);

it.each(BUILD_STATUSES)("accepts generated %s status URL filters", (status) => {
  expect(parseBuildStatusFilter(status)).toBe(status);
});

it.each([null, "", "Ready", "ready", "UNKNOWN"])(
  "rejects invalid status URL filter %s",
  (status) => {
    expect(parseBuildStatusFilter(status)).toBeUndefined();
  },
);

it("sends bounded operation paging and server-side filter values", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse({
      items: [],
      total: 0,
      page: 7,
      page_size: 50,
      policy_change_count: 0,
    }),
  );

  await expect(
    buildApi.operations("build-1", {
      search: "inventory item",
      method: "TRACE",
      scope: "changed",
      page: 7,
      page_size: 50,
    }),
  ).resolves.toMatchObject({ page: 7, total: 0 });
  expect(String(fetchMock.mock.calls[0][0])).toBe(
    "/api/v1/builds/build-1/operations?search=inventory+item&method=TRACE&scope=changed&page=7&page_size=50",
  );
});
