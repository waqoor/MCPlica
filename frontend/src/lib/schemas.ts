import { z } from "zod";

// MCPlica serves a strict CSP without `unsafe-eval`; keep Zod on its
// interpreter path so it never probes or generates JavaScript at runtime.
z.config({ jitless: true });

export { z };
