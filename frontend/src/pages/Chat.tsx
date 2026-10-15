import { FormEvent, useState } from "react";
import { api, ChatResponse } from "@/api";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

type Message = { role: "user" | "assistant"; text: string; detail?: ChatResponse };

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("How much did I spend on groceries in September?");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message) return;
    setMessages((current) => [...current, { role: "user", text: message }]);
    setText("");
    setLoading(true);
    setError("");
    try {
      const response = await api.chat(message);
      const body = response.error || response.answer || "No answer was returned.";
      setMessages((current) => [...current, { role: "assistant", text: body, detail: response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[70vh] flex-col gap-4">
      <PageHeader
        title="Chat"
        description="Answers cite transaction ids. Money moves only when the policy engine allows it."
      />
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <ScrollArea className="flex-1 rounded-lg border bg-card">
        <div className="space-y-3 p-4">
          {messages.length === 0 ? (
            <EmptyState
              title="Ask about spending, bills, or a what-if"
              description="Try: How much did I spend on groceries in September?"
            />
          ) : null}
          {messages.map((message, index) => (
            <Card
              key={index}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[90%] border-primary/20 bg-secondary/60 shadow-none"
                  : "mr-auto max-w-[90%] shadow-none"
              }
            >
              <CardContent className="space-y-2 p-4">
                <Badge variant="outline" className="capitalize">
                  {message.role}
                </Badge>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
                {message.detail?.tool_calls?.length ? (
                  <details className="rounded-md bg-muted/60 p-3 text-sm">
                    <summary className="cursor-pointer font-medium">Tool calls and evidence</summary>
                    <ul className="mt-2 space-y-2 text-muted-foreground">
                      {message.detail.tool_calls.map((call, callIndex) => (
                        <li key={callIndex}>
                          <span className="font-medium text-foreground">{call.tool}</span> · {call.outcome}
                          {call.tier ? ` · tier ${call.tier}` : ""} · {call.rule_id}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
                {message.detail?.proposals?.length ? (
                  <p className="text-sm text-muted-foreground">
                    Filed {message.detail.proposals.length} proposal(s). Open the Approval Inbox to review them.
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>

      <form onSubmit={onSubmit} className="sticky bottom-0 space-y-2 border-t bg-background pt-3">
        <Textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          aria-label="Message"
          maxLength={4000}
          rows={2}
          placeholder="Ask FinPilot…"
        />
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">Amounts are in USD.</p>
          <Button type="submit" disabled={loading}>
            {loading ? "Working…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  );
}
