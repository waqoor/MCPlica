import { readFileSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const limits = new Map([
    ["logo.png", 250_000],
    ["logo_draw_only.png", 350_000],
]);
let total = 0;
for (const [name, limit] of limits) {
    const path = resolve(root, "src/assets", name);
    const contents = readFileSync(path);
    const bytes = statSync(path).size;
    total += bytes;
    if (bytes > limit) {
        throw new Error(`${name} is ${bytes} bytes; budget is ${limit} bytes`);
    }
    const pngSignature = "89504e470d0a1a0a";
    if (contents.subarray(0, 8).toString("hex") !== pngSignature) {
        throw new Error(`${name} is not a PNG file`);
    }
    const colorType = contents[25];
    if (colorType !== 4 && colorType !== 6) {
        throw new Error(`${name} does not carry an alpha channel`);
    }
    process.stdout.write(`${name}: ${bytes}/${limit} bytes\n`);
}
if (total > 600_000) {
    throw new Error(
        `Brand assets total ${total} bytes; budget is 600000 bytes`,
    );
}

for (const relativePath of ["index.html", "src/components/brand-logo.tsx"]) {
    const source = readFileSync(resolve(root, relativePath), "utf8");
    if (/logo(?:_draw_only)?\.webp/.test(source)) {
        throw new Error(
            `${relativePath} references a derived WebP instead of the supplied transparent PNG`,
        );
    }
}
