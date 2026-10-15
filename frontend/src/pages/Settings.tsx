import { useEffect, useState } from "react";
import { api, Permission } from "../api";

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

  if (loading) return <p>Loading permission tiers…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-serif text-4xl">Settings</h1>
      <p className="text-sm text-ink/70">
        Tiers are enforced in code, outside the model. T0 is read-only, T1 proposes, T2 needs your approval, T3 can act inside the caps.
      </p>
      {error ? <p className="text-clay">{error}</p> : null}
      {notice ? <p className="text-pine">{notice}</p> : null}
      {rows.length === 0 ? <p>No permission rows.</p> : null}
      {rows.map((row, index) => (
        <form
          key={row.action_type}
          className="grid gap-3 rounded-2xl border border-line bg-card p-4 md:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            save(row);
          }}
        >
          <label className="text-sm">
            Action
            <input className="mt-1 w-full rounded border border-line bg-paper px-2 py-2" value={row.action_type} readOnly />
          </label>
          <label className="text-sm">
            Tier
            <select
              className="mt-1 w-full rounded border border-line px-2 py-2"
              value={row.tier}
              onChange={(event) => update(index, { tier: event.target.value })}
            >
              {tiers.map((tier) => (
                <option key={tier}>{tier}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Per-action limit
            <input
              className="mt-1 w-full rounded border border-line px-2 py-2"
              type="number"
              value={row.per_action_limit ?? ""}
              onChange={(event) =>
                update(index, { per_action_limit: event.target.value === "" ? null : Number(event.target.value) })
              }
            />
          </label>
          <label className="text-sm">
            Daily limit
            <input
              className="mt-1 w-full rounded border border-line px-2 py-2"
              type="number"
              value={row.daily_limit ?? ""}
              onChange={(event) =>
                update(index, { daily_limit: event.target.value === "" ? null : Number(event.target.value) })
              }
            />
          </label>
          <button className="rounded-lg bg-pine px-3 py-2 text-white md:col-span-4 md:w-32">Save</button>
        </form>
      ))}
    </div>
  );
}
