import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = [
    { input: "logo.png", output: "logo.webp", maxWidth: 512 },
    {
        input: "logo_draw_only.png",
        output: "logo_draw_only.webp",
        maxWidth: 192,
    },
];

const browser = await chromium.launch({ headless: true });
try {
    const page = await browser.newPage();
    for (const asset of assets) {
        const input = resolve(root, "src/assets", asset.input);
        const encoded = readFileSync(input).toString("base64");
        const result = await page.evaluate(
            async ({ encoded, maxWidth }) => {
                const image = new Image();
                image.src = `data:image/png;base64,${encoded}`;
                await image.decode();
                const source = document.createElement("canvas");
                source.width = image.naturalWidth;
                source.height = image.naturalHeight;
                const context = source.getContext("2d", {
                    willReadFrequently: true,
                });
                if (!context)
                    throw new Error("Canvas 2D context is unavailable");
                context.drawImage(image, 0, 0);
                const pixels = context.getImageData(
                    0,
                    0,
                    source.width,
                    source.height,
                );
                let left = source.width;
                let right = -1;
                let top = source.height;
                let bottom = -1;
                for (let y = 0; y < source.height; y += 1) {
                    for (let x = 0; x < source.width; x += 1) {
                        if (pixels.data[(y * source.width + x) * 4 + 3] === 0)
                            continue;
                        left = Math.min(left, x);
                        right = Math.max(right, x);
                        top = Math.min(top, y);
                        bottom = Math.max(bottom, y);
                    }
                }
                if (right < left || bottom < top)
                    throw new Error("Logo is fully transparent");
                const cropWidth = right - left + 1;
                const cropHeight = bottom - top + 1;
                const scale = Math.min(1, maxWidth / cropWidth);
                const output = document.createElement("canvas");
                output.width = Math.max(1, Math.round(cropWidth * scale));
                output.height = Math.max(1, Math.round(cropHeight * scale));
                output
                    .getContext("2d")
                    ?.drawImage(
                        source,
                        left,
                        top,
                        cropWidth,
                        cropHeight,
                        0,
                        0,
                        output.width,
                        output.height,
                    );
                const blob = await new Promise((resolveBlob, reject) =>
                    output.toBlob(
                        (value) =>
                            value
                                ? resolveBlob(value)
                                : reject(new Error("WebP encoding failed")),
                        "image/webp",
                        0.9,
                    ),
                );
                return {
                    encoded: btoa(
                        String.fromCharCode(
                            ...new Uint8Array(await blob.arrayBuffer()),
                        ),
                    ),
                    width: output.width,
                    height: output.height,
                };
            },
            { encoded, maxWidth: asset.maxWidth },
        );
        writeFileSync(
            resolve(root, "src/assets", asset.output),
            Buffer.from(result.encoded, "base64"),
        );
        process.stdout.write(
            `${asset.output}: ${result.width}x${result.height}\n`,
        );
    }
} finally {
    await browser.close();
}
