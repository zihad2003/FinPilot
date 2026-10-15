import { FormEvent, useState } from "react";
import { api, ChatResponse } from "../api";

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
      const messageText = err instanceof Error ? err.message : "Chat failed.";
      setError(messageText);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="font-serif text-4xl">Chat</h1>
      <p className="text-sm text-ink/70">
        Answers cite transaction ids. Money moves only when the policy engine allows it.
      </p>
      {error ? <p className="text-clay">{error}</p> : null}
      <div className="space-y-3">
        {messages.length === 0 ? <p className="text-sm">Ask about spending, bills, or a what-if.</p> : null}
        {messages.map((message, index) => (
          <article key={index} className="rounded-2xl border border-line bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-ink/50">{message.role}</p>
            <p className="mt-2 whitespace-pre-wrap">{message.text}</p>
            {message.detail?.tool_calls?.length ? (
              <details className="mt-3 text-sm">
                <summary>Tool calls and evidence</summary>
                <ul className="mt-2 space-y-2">
                  {message.detail.tool_calls.map((call, callIndex) => (
                    <li key={callIndex}>
                      <span className="font-semibold">{call.tool}</span> · {call.outcome}
                      {call.tier ? ` · tier ${call.tier}` : ""} · {call.rule_id}
                      {call.result && "transactions" in call.result ? (
                        <span> · cited inside the result</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
            {message.detail?.proposals?.length ? (
              <p className="mt-2 text-sm">
                Filed {message.detail.proposals.length} proposal(s). Open the Approval Inbox to review them.
              </p>
            ) : null}
          </article>
        ))}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          className="flex-1 rounded-xl border border-line bg-white px-3 py-2"
          value={text}
          onChange={(event) => setText(event.target.value)}
          aria-label="Message"
          maxLength={4000}
        />
        <button className="rounded-xl bg-pine px-4 py-2 text-white disabled:opacity-50" disabled={loading}>
          {loading ? "Working…" : "Send"}
        </button>
      </form>
      <p className="text-xs text-ink/50">Amounts are in USD.</p>
    </div>
  );
}
