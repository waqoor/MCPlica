import type { ValidationReport } from "@/api/contracts";
import { Alert } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

export function ValidationSummary({ report }: { report: ValidationReport }) {
  const valid =
    report.overall_status === "pass" &&
    report.coverage_percent === 100 &&
    report.blocking_error_count === 0;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Coverage" value={`${report.coverage_percent}%`} />
        <Metric label="Source" value={report.operation_source_count} />
        <Metric label="Excluded" value={report.operation_excluded_count} />
        <Metric label="Generated" value={report.operation_generated_count} />
        <Metric label="Blocking" value={report.blocking_error_count} />
      </div>
      {valid ? (
        <Alert title="Validation passed" tone="success">
          All expected source operations are represented after explicit
          exclusions.
        </Alert>
      ) : (
        <Alert title="Deployment blocked" tone="danger">
          Coverage or deterministic validation has not passed. Semantic findings
          cannot override a structural failure.
        </Alert>
      )}
      <div className="space-y-3">
        {report.findings.map((finding, index) => (
          <Card
            className="p-4"
            key={`${finding.code}-${finding.operation_key}-${index}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    tone={
                      finding.severity === "error"
                        ? "danger"
                        : finding.severity === "warning"
                          ? "warning"
                          : "info"
                    }
                  >
                    {finding.severity}
                  </Badge>
                  <code className="font-mono text-xs text-foreground">
                    {finding.code}
                  </code>
                  <span className="text-xs text-muted">{finding.stage}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-foreground">
                  {finding.message}
                </p>
                {finding.operation_key && (
                  <p className="mt-1 font-mono text-xs text-muted">
                    {finding.operation_key}
                  </p>
                )}
              </div>
            </div>
          </Card>
        ))}
        {report.findings.length === 0 && (
          <p className="text-sm text-muted">
            No validation findings were recorded.
          </p>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="p-4">
      <p className="font-mono text-[0.63rem] uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
    </Card>
  );
}
