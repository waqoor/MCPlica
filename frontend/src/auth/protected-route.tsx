import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ApiError } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { useAuth } from "./use-auth";

export function ProtectedRoute() {
  const { user, isLoading, error, refresh } = useAuth();
  const location = useLocation();

  if (isLoading) return <PageSpinner label="Checking your session" />;
  if (
    !user &&
    (!error || (error instanceof ApiError && error.status === 401))
  ) {
    return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  }
  if (!user) {
    return (
      <main className="mx-auto grid min-h-screen max-w-xl place-items-center p-6">
        <Alert title="The control plane is unavailable" tone="danger">
          <p>{error?.message ?? "Your session could not be verified."}</p>
          <Button
            className="mt-4"
            onClick={() => void refresh()}
            variant="outline"
          >
            Try again
          </Button>
        </Alert>
      </main>
    );
  }
  return <Outlet />;
}

export function AdminRoute() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate replace to="/" />;
  return <Outlet />;
}
