import { ErrorNotice } from "./error-notice";
import { PageSpinner } from "./ui/spinner";

export function QueryError({
  error,
  onRetry,
  title = "This data could not be loaded",
}: {
  error: Error;
  onRetry?: () => void;
  title?: string;
}) {
  return <ErrorNotice error={error} onRetry={onRetry} title={title} />;
}

export function QueryPending({ label = "Loading data" }: { label?: string }) {
  return <PageSpinner label={label} />;
}
