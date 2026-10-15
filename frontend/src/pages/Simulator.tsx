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
import { api, Scenario, usd } from "../api";

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
    <div className="space-y-4">
      <h1 className="font-serif text-4xl">What-if</h1>
      <p className="max-w-3xl text-sm text-ink/70">
        This recomputes the next three months from your history. It does not move money.
      </p>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset.label}
            className="rounded-lg bg-pine px-3 py-2 text-white disabled:opacity-50"
            disabled={loading}
            onClick={() => run(preset.changes)}
          >
            {preset.label}
          </button>
        ))}
      </div>
      {loading ? <p>Running the scenario…</p> : null}
      {error ? <p className="text-clay">{error}</p> : null}
      {!result && !loading ? <p className="text-sm">Choose a scenario to compare before and after.</p> : null}
      {result ? (
        <>
          <p>{result.narrative}</p>
          <p className="text-sm text-ink/70">{result.explanation}</p>
          <p className="font-serif text-2xl">
            About {usd(result.monthly_savings)} a month, {usd(result.projected_savings)} over three months.
          </p>
          {result.goal ? (
            <p className="text-sm">
              {result.goal.name} would move from {usd(result.goal.before)} to {usd(result.goal.after)} if that extra went to the goal.
            </p>
          ) : null}
          <div className="h-80 rounded-2xl border border-line bg-card p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bars}>
                <CartesianGrid stroke="#e4dccb" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="before" fill="#c9d7cc" name="Before" />
                <Bar dataKey="after" fill="#1f6b4a" name="After" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="h-64 rounded-2xl border border-line bg-card p-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={line}>
                <CartesianGrid stroke="#e4dccb" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="savings" stroke="#1f6b4a" name="Projected savings" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : null}
    </div>
  );
}
