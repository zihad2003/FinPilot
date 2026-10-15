import { useEffect, useState } from "react";
import { api, Permission } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { LoadingBlock } from "@/components/LoadingBlock";
import { EmptyState } from "@/components/EmptyState";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const tiers = ["T0", "T1", "T2", "T3"];

export default function Settings() {
  const [rows, setRows] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api
      .permissions()
      .then(setRows)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function update(index: number, patch: Partial<Permission>) {
    setRows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)));
  }

  async function save(row: Permission) {
    setError("");
    try {
      await api.savePermission(row);
      setNotice(`Saved ${row.action_type} at ${row.tier}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    }
  }

  if (loading) return <LoadingBlock rows={3} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Settings"
        description="Tiers are enforced in code, outside the model. T0 is read-only, T1 proposes, T2 needs your approval, T3 can act inside the caps."
      />
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}
      {rows.length === 0 ? <EmptyState title="No permission rows" /> : null}
      {rows.map((row, index) => (
        <Card key={row.action_type}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save(row);
            }}
          >
            <CardHeader>
              <CardTitle className="font-mono text-base">{row.action_type}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor={`tier-${row.action_type}`}>Tier</Label>
                <select
                  id={`tier-${row.action_type}`}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={row.tier}
                  onChange={(event) => update(index, { tier: event.target.value })}
                >
                  {tiers.map((tier) => (
                    <option key={tier}>{tier}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor={`per-${row.action_type}`}>Per-action limit</Label>
                <Input
                  id={`per-${row.action_type}`}
                  type="number"
                  value={row.per_action_limit ?? ""}
                  onChange={(event) =>
                    update(index, { per_action_limit: event.target.value === "" ? null : Number(event.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor={`daily-${row.action_type}`}>Daily limit</Label>
                <Input
                  id={`daily-${row.action_type}`}
                  type="number"
                  value={row.daily_limit ?? ""}
                  onChange={(event) =>
                    update(index, { daily_limit: event.target.value === "" ? null : Number(event.target.value) })
                  }
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit">Save</Button>
            </CardFooter>
          </form>
        </Card>
      ))}
    </div>
  );
}
