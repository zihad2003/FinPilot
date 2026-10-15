import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, Scenario } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Money } from "@/components/Money";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const presets = [
  {
    label: "Cancel two subscriptions and cook more",
    changes: [
      { op: "cancel_merchant", merchant: "NETFLIX.COM" },
      { op: "cancel_merchant", merchant: "SPOTIFY USA" },
      { op: "reduce_category", category: "dining", amount: 10 },
    ],
  },
  {
    label: "Cut dining by 20",
    changes: [{ op: "reduce_category", category: "dining", amount: 20 }],
  },
];

export default function Simulator() {
  const [result, setResult] = useState<Scenario | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(changes: { op: string; merchant?: string; category?: string; amount?: number }[]) {
    setLoading(true);
    setError("");
    try {
      setResult(await api.simulate(changes));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setLoading(false);
    }
  }

  const bars = result
    ? Object.keys(result.before_by_category)
        .map((category) => ({
          name: category,
          before: result.before_by_category[category],
          after: result.after_by_category[category],
        }))
        .filter((row) => row.before > 0 || row.after > 0)
    : [];
  const line = result?.savings_by_month.map((value, index) => ({ month: `Month ${index + 1}`, savings: value })) || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="What-if"
        description="This recomputes the next three months from your history. It does not move money."
      />
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <Button key={preset.label} disabled={loading} onClick={() => run(preset.changes)}>
            {preset.label}
          </Button>
        ))}
      </div>
      {loading ? <Skeleton className="h-40 w-full" /> : null}
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {!result && !loading ? (
        <EmptyState title="Choose a scenario" description="Compare before and after without moving money." />
      ) : null}
      {result ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>
                About <Money value={result.monthly_savings} /> a month
              </CardTitle>
              <CardDescription>
                <Money value={result.projected_savings} /> over three months. {result.explanation}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>{result.narrative}</p>
              {result.goal ? (
                <p className="text-muted-foreground">
                  {result.goal.name} would move from <Money value={result.goal.before} /> to{" "}
                  <Money value={result.goal.after} /> if that extra went to the goal.
                </p>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Category before / after</CardTitle>
            </CardHeader>
            <CardContent className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bars}>
                  <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="before" fill="hsl(var(--secondary))" name="Before" />
                  <Bar dataKey="after" fill="hsl(var(--primary))" name="After" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Projected savings</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={line}>
                  <CartesianGrid stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="savings" stroke="hsl(var(--primary))" name="Projected savings" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
