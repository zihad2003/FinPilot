import { useEffect, useState } from "react";
import { api, Proposal, usd } from "../api";

export default function Inbox() {
  const [rows, setRows] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [amounts, setAmounts] = useState<Record<number, string>>({});

  function load() {
    setLoading(true);
    api
      .proposals()
      .then((proposals) => {
        setRows(proposals);
        setError("");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function approve(id: number) {
    setNotice("");
    setError("");
    try {
      const result = await api.approve(id);
      setNotice(
        result.executed
          ? `Approved. Checking is now ${usd(result.result?.balance || 0)}.`
          : result.reason,
      );
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    }
  }

  async function reject(id: number) {
    setError("");
    try {
      await api.reject(id);
      setNotice("Proposal rejected. No money moved.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed.");
    }
  }

  async function saveAmount(id: number) {
    const amount = Number(amounts[id]);
    if (!amount) return;
    try {
      await api.editProposal(id, amount);
      setNotice("Amount updated. Approval still has to pass the policy limits.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Edit failed.");
    }
  }

  if (loading) return <p>Loading the inbox…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-serif text-4xl">Approval Inbox</h1>
      <p className="text-sm text-ink/70">Cards expire 15 minutes after they are created. T1 proposals cannot be executed.</p>
      {error ? <p className="text-clay">{error}</p> : null}
      {notice ? <p className="text-pine">{notice}</p> : null}
      {rows.length === 0 ? <p>No proposals yet. The inbox is empty.</p> : null}
      {rows.map((row) => (
        <article key={row.id} className="rounded-2xl border border-line bg-card p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-serif text-2xl">
              {row.action_type.replaceAll("_", " ")} · {usd(Number(row.payload.amount || 0))}
            </h2>
            <span className="rounded-full bg-moss px-3 py-1 text-sm">{row.status}</span>
          </div>
          <p className="mt-2">{row.reason}</p>
          <p className="mt-2 text-sm">{row.expected_effect}</p>
          <p className="mt-2 text-sm text-ink/70">
            Policy rule {row.rule_id}. Evidence transactions {(row.evidence_ids || []).map((id) => `#${id}`).join(", ") || "none"}.
          </p>
          {row.status === "pending" ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button className="rounded-lg bg-pine px-3 py-2 text-white" onClick={() => approve(row.id)}>
                Approve
              </button>
              <button className="rounded-lg border border-line px-3 py-2" onClick={() => reject(row.id)}>
                Reject
              </button>
              <input
                className="w-28 rounded-lg border border-line px-2 py-2"
                aria-label="Edit amount"
                placeholder="New amount"
                value={amounts[row.id] || ""}
                onChange={(event) => setAmounts({ ...amounts, [row.id]: event.target.value })}
              />
              <button className="rounded-lg border border-line px-3 py-2" onClick={() => saveAmount(row.id)}>
                Edit
              </button>
            </div>
          ) : (
            <p className="mt-3 text-sm">This card cannot move money in its current state.</p>
          )}
        </article>
      ))}
    </div>
  );
}
