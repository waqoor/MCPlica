import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const check = process.argv.includes("--check");
const tempRoot = check
    ? mkdtempSync(join(tmpdir(), "mcplica-api-contract-"))
    : null;
const outputRoot = tempRoot ?? resolve(frontendRoot, "src/api/generated");
const openapi = resolve(frontendRoot, "../openapi.json");
const template = resolve(frontendRoot, "scripts/openapi-zod-schemas.hbs");
const schemaOutput = resolve(outputRoot, "schema.d.ts");
const zodOutput = resolve(outputRoot, "zod.ts");
const constantsOutput = resolve(outputRoot, "constants.ts");

function run(script, args) {
    const result = spawnSync(
        process.execPath,
        [resolve(frontendRoot, script), ...args],
        {
            cwd: frontendRoot,
            encoding: "utf8",
            stdio: "pipe",
        },
    );
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    if (result.status !== 0) process.exit(result.status ?? 1);
}

function normalized(path) {
    return readFileSync(path, "utf8").replaceAll("\r\n", "\n");
}

try {
    const document = JSON.parse(readFileSync(openapi, "utf8"));
    const buildStatuses = document.components?.schemas?.BuildStatus?.enum;
    if (!Array.isArray(buildStatuses) || buildStatuses.length === 0) {
        throw new Error("OpenAPI BuildStatus enum is missing");
    }
    writeFileSync(
        constantsOutput,
        `// Generated from openapi.json. Do not edit by hand.\n` +
            `export const BUILD_STATUSES = ${JSON.stringify(buildStatuses)} as const;\n`,
        "utf8",
    );
    run("node_modules/openapi-typescript/bin/cli.js", [
        openapi,
        "--output",
        schemaOutput,
        "--export-type",
        "--immutable",
        "--alphabetize",
    ]);
    run("node_modules/openapi-zod-client/bin.js", [
        openapi,
        "--template",
        template,
        "--output",
        zodOutput,
        "--export-schemas",
        "--strict-objects",
    ]);
    run("node_modules/prettier/bin/prettier.cjs", [
        "--write",
        schemaOutput,
        zodOutput,
        constantsOutput,
    ]);

    if (check) {
        const trackedRoot = resolve(frontendRoot, "src/api/generated");
        const stale = ["schema.d.ts", "zod.ts", "constants.ts"].filter(
            (name) =>
                normalized(resolve(tempRoot, name)) !==
                normalized(resolve(trackedRoot, name)),
        );
        if (stale.length) {
            process.stderr.write(
                `Generated API contracts are stale: ${stale.join(", ")}. Run pnpm generate:api.\n`,
            );
            process.exitCode = 1;
        }
    }
} finally {
    if (tempRoot) rmSync(tempRoot, { recursive: true, force: true });
}
