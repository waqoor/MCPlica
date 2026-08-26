import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function RouteErrorPage() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? error.statusText
    : error instanceof Error
      ? error.message
      : "The page could not be rendered.";
  return (
    <main className="mx-auto grid min-h-screen max-w-xl place-items-center p-6">
      <Alert title="Route failed" tone="danger">
        <p>{message}</p>
        <Button
          className="mt-4"
          onClick={() => window.location.assign("/")}
          variant="outline"
        >
          Return to dashboard
        </Button>
      </Alert>
    </main>
  );
}
