import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CATEGORIES, Summary, usd } from "../api";

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

  if (loading) return <p>Loading the sandbox account…</p>;
  if (error) return <p className="text-clay">Could not load the dashboard. {error}</p>;
  if (!data) return <p>No account data yet.</p>;

  const spend = data.budget.categories.filter((row) => row.actual > 0);
  const chart = data.budget.categories
    .filter((row) => row.category !== "savings")
    .map((row) => ({ name: row.category, limit: row.limit, actual: row.actual }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-4xl">October budget</h1>
        <p className="mt-2 max-w-3xl text-sm text-ink/70">{data.budget.explanation}</p>
      </header>
      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl border border-line bg-card p-4">
          <p className="text-sm text-ink/60">Checking</p>
          <p className="num font-serif text-3xl">{usd(data.account.balance)}</p>
          <p className="text-sm">{data.account.account_number_masked}</p>
        </article>
        <article className="rounded-2xl border border-line bg-card p-4">
          <p className="text-sm text-ink/60">Allowance</p>
          <p className="num font-serif text-3xl">{usd(data.budget.income)}</p>
          <p className="text-sm">50/30/20 baseline is the starting point</p>
        </article>
        <article className="rounded-2xl border border-line bg-card p-4">
          <p className="text-sm text-ink/60">Flags</p>
          <p className="num font-serif text-3xl">{data.anomalies.length}</p>
          <p className="text-sm">Duplicates, price hikes, unusual charges</p>
        </article>
      </section>

      <section className="rounded-2xl border border-line bg-card p-4">
        <h2 className="font-serif text-2xl">Budget versus actual</h2>
        {chart.length === 0 ? (
          <p className="mt-4 text-sm">No budget rows yet.</p>
        ) : (
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart}>
                <CartesianGrid stroke="#e4dccb" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="limit" fill="#c9d7cc" name="Limit" />
                <Bar dataKey="actual" fill="#1f6b4a" name="Actual" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-line bg-card p-4">
          <h2 className="font-serif text-2xl">Goals</h2>
          {data.goals.length === 0 ? (
            <p className="mt-3 text-sm">No savings goals yet.</p>
          ) : (
            data.goals.map((goal) => (
              <div key={goal.id} className="mt-4">
                <div className="flex justify-between text-sm">
                  <span>{goal.name}</span>
                  <span className="num">
                    {usd(goal.current_amount)} / {usd(goal.target_amount)}
                  </span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-moss">
                  <div className="h-2 rounded-full bg-pine" style={{ width: `${Math.min(100, goal.progress * 100)}%` }} />
                </div>
                <p className="mt-1 text-sm text-ink/70">Suggested weekly {usd(goal.suggested_weekly)}</p>
              </div>
            ))
          )}
        </article>
        <article className="rounded-2xl border border-line bg-card p-4">
          <h2 className="font-serif text-2xl">This month by category</h2>
          {spend.length === 0 ? (
            <p className="mt-3 text-sm">No spending posted this month.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {spend.map((row) => (
                <li key={row.category} className="flex justify-between">
                  <span>{row.category}</span>
                  <span className="num">{usd(row.actual)}</span>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>

      <section className="rounded-2xl border border-line bg-card p-4">
        <h2 className="font-serif text-2xl">Anomalies</h2>
        {data.anomalies.length === 0 ? (
          <p className="mt-3 text-sm">Nothing unusual in the current ledger.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {data.anomalies.map((item, index) => (
              <li key={`${item.type}-${index}`}>
                <span className="font-semibold">{item.type.replaceAll("_", " ")}.</span> {item.detail}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-line bg-card p-4">
        <h2 className="font-serif text-2xl">Recent transactions</h2>
        {data.recent_transactions.length === 0 ? (
          <p className="mt-3 text-sm">No transactions yet.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-ink/60">
              <tr>
                <th className="py-2">Date</th>
                <th>Merchant</th>
                <th>Category</th>
                <th className="text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_transactions.map((txn) => (
                <tr key={txn.id} className="border-t border-line">
                  <td className="py-2">{txn.date}</td>
                  <td>{txn.merchant}</td>
                  <td>
                    <select
                      aria-label={`Category for ${txn.merchant}`}
                      className="rounded border border-line bg-white px-2 py-1"
                      value={txn.category || "other"}
                      onChange={(event) => api.correct(txn.id, event.target.value).then(load)}
                    >
                      {CATEGORIES.map((category) => (
                        <option key={category}>{category}</option>
                      ))}
                    </select>
                  </td>
                  <td className="num text-right">{usd(txn.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-2xl border border-line bg-card p-4">
        <h2 className="font-serif text-2xl">Recent agent actions</h2>
        {data.recent_actions.length === 0 ? (
          <p className="mt-3 text-sm">No actions logged yet.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {data.recent_actions.map((row) => (
              <li key={row.id}>
                {row.tool} · {row.policy_outcome} · {row.rule_id}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
