import { expect, test } from "vitest";
import type { Build, User } from "@/api/contracts";
import { buildCanDeploy, canDeploy } from "./lifecycle";

const readyBuild = { status: "READY" } as Build;
const failedBuild = { status: "FAILED" } as Build;
const admin = { role: "admin" } as User;
const builder = { role: "builder" } as User;

test("deploy remains blocked until both build and inbound access are ready", () => {
  expect(buildCanDeploy(readyBuild, true)).toBe(true);
  expect(buildCanDeploy(readyBuild, false)).toBe(false);
  expect(buildCanDeploy(failedBuild, true)).toBe(false);
});

test("builder deployment permission fails closed", () => {
  expect(canDeploy(admin, false)).toBe(true);
  expect(canDeploy(builder, false)).toBe(false);
  expect(canDeploy(builder, true)).toBe(true);
});
