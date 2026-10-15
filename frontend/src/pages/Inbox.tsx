import { useEffect, useState } from "react";
import { api, Proposal } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { LoadingBlock } from "@/components/LoadingBlock";
import { EmptyState } from "@/components/EmptyState";
import { Money } from "@/components/Money";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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
      if (result.executed && result.result?.balance != null) {
        setNotice(
          `Approved. Checking is now ${result.result.balance.toLocaleString("en-US", {
            style: "currency",
            currency: "USD",
          })}.`,
        );
      } else {
        setNotice(result.reason || "Approved.");
      }
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

  if (loading) return <LoadingBlock rows={3} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Approval Inbox"
        description="Cards expire 15 minutes after they are created. T1 proposals cannot be executed."
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
      {rows.length === 0 ? (
        <EmptyState title="Nothing to approve" description="When the agent proposes a bill or transfer, it will show up here." />
      ) : null}
      {rows.map((row) => (
        <Card key={row.id}>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 space-y-0">
            <div>
              <CardTitle className="capitalize">
                {row.action_type.replaceAll("_", " ")} · <Money value={Number(row.payload.amount || 0)} />
              </CardTitle>
              <CardDescription className="mt-1">{row.expected_effect}</CardDescription>
            </div>
            <Badge variant={row.status === "pending" ? "default" : "secondary"}>{row.status}</Badge>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>{row.reason}</p>
            <p className="text-muted-foreground">
              Policy rule <span className="font-medium text-foreground">{row.rule_id}</span>. Evidence{" "}
              {(row.evidence_ids || []).map((id) => `#${id}`).join(", ") || "none"}.
            </p>
          </CardContent>
          {row.status === "pending" ? (
            <CardFooter className="flex flex-wrap items-center gap-2">
              <Button onClick={() => approve(row.id)}>Approve</Button>
              <Button variant="outline" onClick={() => reject(row.id)}>
                Reject
              </Button>
              <Input
                className="w-28"
                aria-label="Edit amount"
                placeholder="New amount"
                value={amounts[row.id] || ""}
                onChange={(event) => setAmounts({ ...amounts, [row.id]: event.target.value })}
              />
              <Button variant="secondary" onClick={() => saveAmount(row.id)}>
                Edit
              </Button>
            </CardFooter>
          ) : (
            <CardFooter>
              <p className="text-sm text-muted-foreground">This card cannot move money in its current state.</p>
            </CardFooter>
          )}
        </Card>
      ))}
    </div>
  );
}
