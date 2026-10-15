import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CATEGORIES, Summary } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { LoadingBlock } from "@/components/LoadingBlock";
import { EmptyState } from "@/components/EmptyState";
import { Money } from "@/components/Money";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function Dashboard() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api
      .summary()
      .then((summary) => {
        setData(summary);
        setError("");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  if (loading) return <LoadingBlock rows={4} />;
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Could not load the dashboard. {error}</AlertDescription>
      </Alert>
    );
  }
  if (!data) return <EmptyState title="No account data yet" description="Seed the sandbox database to begin." />;

  const spend = data.budget.categories.filter((row) => row.actual > 0);
  const chart = data.budget.categories
    .filter((row) => row.category !== "savings")
    .map((row) => ({ name: row.category, limit: row.limit, actual: row.actual }));

  return (
    <div className="space-y-6">
      <PageHeader title="October budget" description={data.budget.explanation} />

      <section className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Checking</CardDescription>
            <CardTitle className="text-3xl">
              <Money value={data.account.balance} />
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{data.account.account_number_masked}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Allowance</CardDescription>
            <CardTitle className="text-3xl">
              <Money value={data.budget.income} />
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">50/30/20 as the baseline</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Flags</CardDescription>
            <CardTitle className="text-3xl">{data.anomalies.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Duplicates, price hikes, unusual charges</CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Budget versus actual</CardTitle>
        </CardHeader>
        <CardContent>
          {chart.length === 0 ? (
            <EmptyState title="No budget rows yet" />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="limit" fill="hsl(var(--secondary))" name="Limit" />
                  <Bar dataKey="actual" fill="hsl(var(--primary))" name="Actual" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Goals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.goals.length === 0 ? (
              <p className="text-sm text-muted-foreground">No savings goals yet.</p>
            ) : (
              data.goals.map((goal) => (
                <div key={goal.id}>
                  <div className="flex justify-between text-sm">
                    <span>{goal.name}</span>
                    <span>
                      <Money value={goal.current_amount} /> / <Money value={goal.target_amount} />
                    </span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-secondary">
                    <div
                      className="h-2 rounded-full bg-primary transition-all"
                      style={{ width: `${Math.min(100, goal.progress * 100)}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Suggested weekly <Money value={goal.suggested_weekly} />
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>This month by category</CardTitle>
          </CardHeader>
          <CardContent>
            {spend.length === 0 ? (
              <p className="text-sm text-muted-foreground">No spending posted this month.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {spend.map((row) => (
                  <li key={row.category} className="flex justify-between border-b border-border/60 py-2 last:border-0">
                    <span className="capitalize">{row.category}</span>
                    <Money value={row.actual} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Anomalies</CardTitle>
        </CardHeader>
        <CardContent>
          {data.anomalies.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing unusual in the current ledger.</p>
          ) : (
            <ul className="space-y-3">
              {data.anomalies.map((item, index) => (
                <li key={`${item.type}-${index}`} className="flex flex-wrap items-start gap-2 text-sm">
                  <Badge variant="secondary">{item.type.replaceAll("_", " ")}</Badge>
                  <span className="text-muted-foreground">{item.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_transactions.length === 0 ? (
            <EmptyState title="No transactions yet" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Merchant</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_transactions.map((txn) => (
                  <TableRow key={txn.id}>
                    <TableCell>{txn.date}</TableCell>
                    <TableCell>{txn.merchant}</TableCell>
                    <TableCell>
                      <select
                        aria-label={`Category for ${txn.merchant}`}
                        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                        value={txn.category || "other"}
                        onChange={(event) => api.correct(txn.id, event.target.value).then(load)}
                      >
                        {CATEGORIES.map((category) => (
                          <option key={category}>{category}</option>
                        ))}
                      </select>
                    </TableCell>
                    <TableCell className="text-right">
                      <Money value={txn.amount} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent agent actions</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_actions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No actions logged yet.</p>
          ) : (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {data.recent_actions.map((row) => (
                <li key={row.id} className="flex flex-wrap gap-2">
                  <span className="font-medium text-foreground">{row.tool}</span>
                  <Badge variant="outline">{row.policy_outcome}</Badge>
                  <span>{row.rule_id}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
