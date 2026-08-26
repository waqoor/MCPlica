import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";

export function SafeMarkdown({ children }: { children: string }) {
  return (
    <div className="prose-safe text-sm leading-7 text-muted">
      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{children}</ReactMarkdown>
    </div>
  );
}
