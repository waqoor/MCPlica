import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { useState } from "react";
import { usageApi } from "@/api/usage";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { SettingsNavigation } from "@/components/settings-navigation";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/format";

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatTokens(value: number): string {
  return value.toLocaleString();
}

export function UsagePage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [logsModel, setLogsModel] = useState<string | null>(null);
  const isoFrom = from ? new Date(from).toISOString() : undefined;
  const isoTo = to ? new Date(to).toISOString() : undefined;
  const usage = useQuery({
    queryKey: ["usage", "by-model", { from, to }],
    queryFn: ({ signal }) =>
      usageApi.byModel({ from: isoFrom, to: isoTo }, signal),
  });
  const totalTokens =
    usage.data?.reduce((sum, row) => sum + row.total_tokens, 0) ?? 0;
  const totalCost =
    usage.data?.reduce((sum, row) => sum + row.total_cost, 0) ?? 0;
  const totalCalls =
    usage.data?.reduce((sum, row) => sum + row.call_count, 0) ?? 0;
  return (
    <div className="space-y-7">
      <PageHeader
        description="Token and cost usage per AI model, from recorded build activity."
        eyebrow="Settings"
        title="Usage"
      />
      <SettingsNavigation canManageInstallation />
      <Card className="max-w-3xl">
        <CardHeader>
          <div>
            <CardTitle>Filter by date</CardTitle>
            <p className="mt-1 text-xs text-muted">
              Leave both empty to see all-time usage.
            </p>
          </div>
        </CardHeader>
        <div className="flex flex-wrap gap-4">
          <div className="space-y-2">
            <Label htmlFor="usage-from">From</Label>
            <Input
              id="usage-from"
              onChange={(event) => setFrom(event.target.value)}
              type="date"
              value={from}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="usage-to">To</Label>
            <Input
              id="usage-to"
              onChange={(event) => setTo(event.target.value)}
              type="date"
              value={to}
            />
          </div>
        </div>
      </Card>
      {usage.isPending && <QueryPending label="Loading usage" />}
      {usage.error && (
        <QueryError error={usage.error} onRetry={() => void usage.refetch()} />
      )}
      {usage.data && usage.data.length === 0 && (
        <EmptyState
          description="No AI calls have been recorded for this date range."
          icon={Gauge}
          title="No usage found"
        />
      )}
      {usage.data && usage.data.length > 0 && (
        <div className="max-w-full overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[42rem] text-left">
            <thead className="bg-panel-raised font-mono text-[0.64rem] uppercase tracking-[0.1em] text-muted">
              <tr>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Calls</th>
                <th className="px-4 py-3">Total tokens</th>
                <th className="px-4 py-3">Total cost</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Logs</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-panel">
              {usage.data.map((row) => (
                <tr className="hover:bg-panel-hover/50" key={row.model}>
                  <td
                    className={
                      row.is_attributable
                        ? "px-4 py-4 text-sm font-medium text-foreground"
                        : "px-4 py-4 text-sm italic text-muted"
                    }
                  >
                    {row.model}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {row.call_count}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {formatTokens(row.total_tokens)}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {formatCost(row.total_cost)}
                  </td>
                  <td className="px-4 py-4 text-right">
                    {row.is_attributable ? (
                      <Button
                        onClick={() => setLogsModel(row.model)}
                        size="sm"
                        variant="outline"
                      >
                        View logs
                      </Button>
                    ) : (
                      <span className="text-xs text-muted">
                        not attributable to one model
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-border bg-panel-raised">
              <tr>
                <td className="px-4 py-3 text-sm font-semibold text-foreground">
                  Total
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-foreground">
                  {totalCalls}
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-foreground">
                  {formatTokens(totalTokens)}
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-foreground">
                  {formatCost(totalCost)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <UsageLogsDialog
        from={isoFrom}
        model={logsModel}
        onClose={() => setLogsModel(null)}
        to={isoTo}
      />
    </div>
  );
}

function UsageLogsDialog({
  model,
  from,
  to,
  onClose,
}: {
  model: string | null;
  from: string | undefined;
  to: string | undefined;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const logs = useQuery({
    enabled: model !== null,
    queryKey: ["usage", "logs", model, { from, to, page }],
    queryFn: ({ signal }) =>
      usageApi.logs({ model: model!, from, to, page, page_size: 50 }, signal),
  });
  const pageCount = logs.data
    ? Math.max(1, Math.ceil(logs.data.total / logs.data.page_size))
    : 1;
  return (
    <Dialog
      description={model ?? undefined}
      onClose={() => {
        setPage(1);
        onClose();
      }}
      open={model !== null}
      title="Usage logs"
    >
      {logs.isPending && <QueryPending label="Loading usage logs" />}
      {logs.error && (
        <QueryError error={logs.error} onRetry={() => void logs.refetch()} />
      )}
      {logs.data && logs.data.items.length === 0 && (
        <p className="text-sm text-muted">
          No calls recorded for this model in this date range.
        </p>
      )}
      {logs.data && logs.data.items.length > 0 && (
        <div className="space-y-4">
          <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-panel-raised font-mono text-[0.6rem] uppercase tracking-[0.1em] text-muted">
                <tr>
                  <th className="px-3 py-2">Stage</th>
                  <th className="px-3 py-2">Operation</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Latency</th>
                  <th className="px-3 py-2">When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-panel">
                {logs.data.items.map((run) => (
                  <tr key={run.id}>
                    <td className="px-3 py-2 text-xs text-foreground">
                      {run.stage}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">
                      {run.operation_key ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">
                      {run.status}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">
                      {run.latency_ms === null ? "—" : `${run.latency_ms} ms`}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">
                      {formatDate(run.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted">
              Page {page} of {pageCount} · {logs.data.total} total
            </p>
            <div className="flex gap-2">
              <Button
                disabled={page <= 1}
                onClick={() => setPage((current) => current - 1)}
                size="sm"
                variant="outline"
              >
                Previous
              </Button>
              <Button
                disabled={page >= pageCount}
                onClick={() => setPage((current) => current + 1)}
                size="sm"
                variant="outline"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}
