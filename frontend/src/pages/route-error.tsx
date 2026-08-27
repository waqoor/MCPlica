import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { BrandLogo } from "@/components/brand-logo";
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
      <div className="w-full">
        <a
          aria-label="MCPlica dashboard"
          className="mb-6 block w-fit rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
          href="/"
        >
          <BrandLogo alt="" className="h-10 w-[10.5rem]" loading="eager" />
        </a>
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
      </div>
    </main>
  );
}
