import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { BrandLogo } from "@/components/brand-logo";
import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";

export function RouteErrorPage() {
  const error = useRouteError();
  const renderedError = isRouteErrorResponse(error)
    ? new Error(
        error.statusText || "The requested route could not be rendered.",
      )
    : error;
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
        <div>
          <ErrorNotice error={renderedError} title="Route failed" />
          <Button
            className="mt-4"
            onClick={() => window.location.assign("/")}
            variant="outline"
          >
            Return to dashboard
          </Button>
        </div>
      </div>
    </main>
  );
}
