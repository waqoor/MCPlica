export function JsonCode({
  value,
  label = "JSON document",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <pre
      aria-label={label}
      className="scrollbar-thin max-h-[32rem] overflow-auto rounded-lg border border-border bg-canvas p-4 font-mono text-xs leading-6 text-info-soft"
      role="region"
    >
      <code>{JSON.stringify(value, null, 2)}</code>
    </pre>
  );
}
