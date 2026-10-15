import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, AuditRow } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { LoadingBlock } from "@/components/LoadingBlock";
import { EmptyState } from "@/components/EmptyState";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function Audit() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [outcome, setOutcome] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .audit(outcome)
      .then(setRows)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [outcome]);

  async function exportCsv() {
    const csv = await api.exportAudit();
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "finpilot-audit.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit log"
        description="Every policy decision is appended here."
        action={
          <Button variant="outline" onClick={exportCsv}>
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
        }
      />
      <div className="flex items-center gap-2">
        <Label htmlFor="outcome">Outcome</Label>
        <select
          id="outcome"
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={outcome}
          onChange={(event) => setOutcome(event.target.value)}
        >
          <option value="">All</option>
          <option>ALLOW</option>
          <option>REQUIRE_APPROVAL</option>
          <option>DENY</option>
        </select>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {loading ? <LoadingBlock rows={2} /> : null}
      {!loading && rows.length === 0 ? (
        <EmptyState title="No audit rows for this filter" description="Try clearing the outcome filter." />
      ) : null}
      {!loading && rows.length > 0 ? (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Tool</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap">{row.timestamp.replace("T", " ").slice(0, 19)}</TableCell>
                    <TableCell>{row.actor}</TableCell>
                    <TableCell>{row.tool}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{row.policy_outcome}</Badge>
                    </TableCell>
                    <TableCell>{row.rule_id}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">{row.result}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
