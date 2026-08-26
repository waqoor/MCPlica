import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";
import { EmptyState } from "./ui/empty-state";
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
  return (
    <EmptyState
      action={
        onRetry ? (
          <Button onClick={onRetry} variant="outline">
            <RefreshCw aria-hidden="true" className="size-4" />
            Try again
          </Button>
        ) : undefined
      }
      description={error.message || "Check the service status and try again."}
      icon={AlertCircle}
      title={title}
    />
  );
}

export function QueryPending({ label = "Loading data" }: { label?: string }) {
  return <PageSpinner label={label} />;
}
