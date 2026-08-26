import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "@/lib/schemas";
import { useAuth } from "@/auth/use-auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FieldError, FieldHelp, Label } from "@/components/ui/label";

const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const destination = (location.state as { from?: string } | null)?.from ?? "/";

  useEffect(() => {
    document.title = "Sign in · MCPlica";
    return () => {
      document.title = "MCPlica control plane";
    };
  }, []);

  if (user) return <Navigate replace to="/" />;

  async function submit(values: LoginValues) {
    try {
      await login(values);
      navigate(destination.startsWith("/") ? destination : "/", {
        replace: true,
      });
    } catch (error) {
      form.setError("root", {
        message: error instanceof Error ? error.message : "Sign-in failed.",
      });
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden p-4 sm:p-8">
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-info via-accent to-warning"
      />
      <div className="grid w-full max-w-5xl gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <section className="hidden lg:block">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">
            Self-hosted control plane
          </p>
          <h1 className="mt-5 max-w-2xl text-5xl font-semibold leading-[1.06] tracking-[-0.045em] text-foreground">
            Compile API truth into an MCP surface you can prove.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-muted">
            Source structure stays deterministic. Build intelligence stays
            reviewable. Each deployment stays isolated.
          </p>
          <div className="mt-9 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.12em] text-muted">
            <span className="text-info-soft">Source</span>
            <ArrowRight aria-hidden="true" className="size-3" />
            <span className="text-accent">Canonical</span>
            <ArrowRight aria-hidden="true" className="size-3" />
            <span className="text-warning-soft">Manifest</span>
            <ArrowRight aria-hidden="true" className="size-3" />
            <span className="text-success-soft">Runtime</span>
          </div>
        </section>

        <Card className="mx-auto w-full max-w-md border-border-strong p-6 sm:p-8">
          <div className="mb-7 flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-lg border border-accent/40 bg-accent/10 font-mono font-bold text-accent">
              M
            </span>
            <div>
              <p className="text-lg font-semibold text-foreground">
                Sign in to MCPlica
              </p>
              <p className="text-xs text-muted">
                Installation administrator access
              </p>
            </div>
          </div>

          <form
            className="space-y-5"
            noValidate
            onSubmit={form.handleSubmit(submit)}
          >
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                autoComplete="username"
                autoFocus
                id="email"
                inputMode="email"
                type="email"
                {...form.register("email")}
                aria-invalid={Boolean(form.formState.errors.email)}
              />
              {form.formState.errors.email && (
                <FieldError>{form.formState.errors.email.message}</FieldError>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                autoComplete="current-password"
                id="password"
                type="password"
                {...form.register("password")}
                aria-invalid={Boolean(form.formState.errors.password)}
              />
              {form.formState.errors.password && (
                <FieldError>
                  {form.formState.errors.password.message}
                </FieldError>
              )}
            </div>

            {form.formState.errors.root && (
              <Alert tone="danger">{form.formState.errors.root.message}</Alert>
            )}

            <Button
              className="w-full"
              disabled={form.formState.isSubmitting}
              type="submit"
            >
              <LockKeyhole aria-hidden="true" className="size-4" />
              {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
            <FieldHelp className="text-center">
              Accounts are created by an administrator. Public registration is
              disabled.
            </FieldHelp>
          </form>
        </Card>
      </div>
    </main>
  );
}
