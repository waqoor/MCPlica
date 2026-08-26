import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button-variants";
import { EmptyState } from "@/components/ui/empty-state";

export function NotFoundPage() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <EmptyState
        action={
          <Link className={buttonVariants()} to="/">
            Return to dashboard
          </Link>
        }
        description="The requested control-plane route does not exist or is no longer available."
        icon={Compass}
        title="Page not found"
      />
    </div>
  );
}
