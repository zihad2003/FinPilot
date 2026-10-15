import { useEffect, useState } from "react";
import { api, AuditRow } from "../api";

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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-4xl">Audit log</h1>
          <p className="text-sm text-ink/70">Every policy decision is appended here.</p>
        </div>
        <button className="rounded-lg border border-line bg-white px-3 py-2" onClick={exportCsv}>
          Export CSV
        </button>
      </div>
      <label className="block text-sm">
        Outcome
        <select className="ml-2 rounded border border-line px-2 py-1" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
          <option value="">All</option>
          <option>ALLOW</option>
          <option>REQUIRE_APPROVAL</option>
          <option>DENY</option>
        </select>
      </label>
      {error ? <p className="text-clay">{error}</p> : null}
      {loading ? <p>Loading the log…</p> : null}
      {!loading && rows.length === 0 ? <p>No audit rows for this filter.</p> : null}
      {!loading && rows.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border border-line bg-card">
          <table className="w-full text-left text-sm">
            <thead className="text-ink/60">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th>Actor</th>
                <th>Tool</th>
                <th>Outcome</th>
                <th>Rule</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-line">
                  <td className="px-3 py-2 whitespace-nowrap">{row.timestamp.replace("T", " ").slice(0, 19)}</td>
                  <td>{row.actor}</td>
                  <td>{row.tool}</td>
                  <td>{row.policy_outcome}</td>
                  <td>{row.rule_id}</td>
                  <td>{row.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
