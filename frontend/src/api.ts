export type Account = {
  id: number;
  name: string;
  balance: number;
  currency: string;
  account_number_masked: string | null;
};

export type BudgetRow = {
  category: string;
  limit: number;
  actual: number;
  remaining: number;
};

export type Budget = {
  month: string;
  income: number;
  explanation: string;
  baseline: { needs: number; wants: number; savings: number };
  categories: BudgetRow[];
};

export type Goal = {
  id: number;
  name: string;
  target_amount: number;
  target_date: string;
  current_amount: number;
  progress: number;
  suggested_weekly: number;
  remaining: number;
};

export type Txn = {
  id: number;
  date: string;
  amount: number;
  merchant: string;
  raw_description: string;
  category: string | null;
  confidence: number | null;
  source: string | null;
};

export type AuditRow = {
  id: number;
  timestamp: string;
  actor: string;
  tool: string;
  policy_outcome: string;
  result: string;
  rule_id: string | null;
  idempotency_key: string | null;
};

export type Proposal = {
  id: number;
  action_type: string;
  payload: { payee?: string; amount?: number; date?: string; goal_id?: number };
  reason: string;
  evidence_ids: number[];
  status: string;
  expires_at: string;
  rule_id: string | null;
  expected_effect: string | null;
};

export type Permission = {
  id: number;
  action_type: string;
  tier: string;
  per_action_limit: number | null;
  daily_limit: number | null;
};

export type Anomaly = {
  type: string;
  merchant: string;
  amount: number;
  detail: string;
  transaction_ids: number[];
};

export type Summary = {
  account: Account;
  budget: Budget;
  goals: Goal[];
  anomalies: Anomaly[];
  recent_transactions: Txn[];
  recent_actions: AuditRow[];
};

export type ToolCall = {
  tool: string;
  outcome: string;
  rule_id: string;
  tier: string | null;
  reason: string;
  result: Record<string, unknown> | null;
};

export type ChatResponse = {
  answer: string | null;
  error: string | null;
  tool_calls: ToolCall[];
  proposals: { id: number; status: string; action_type: string; rule_id: string }[];
};

export type Scenario = {
  before_by_category: Record<string, number>;
  after_by_category: Record<string, number>;
  monthly_savings: number;
  projected_savings: number;
  savings_by_month: number[];
  narrative: string;
  explanation: string;
  goal: { name: string; before: number; after: number; target: number } | null;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = { "Content-Type": "application/json", ...(options?.headers || {}) };
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || body.reason || detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/csv")) {
    return (await response.text()) as T;
  }
  return response.json();
}

export const api = {
  summary: () => request<Summary>("/insights/summary"),
  transactions: () => request<Txn[]>("/transactions?limit=40"),
  proposals: (status?: string) => request<Proposal[]>(`/proposals${status ? `?status=${status}` : ""}`),
  approve: (id: number) =>
    request<{ executed: boolean; result: { balance: number } | null; reason: string }>(
      `/proposals/${id}/approve`,
      { method: "POST", headers: { "Idempotency-Key": `ui-approve-${id}-${Date.now()}` } },
    ),
  reject: (id: number) => request<Proposal>(`/proposals/${id}/reject`, { method: "POST" }),
  editProposal: (id: number, amount: number) =>
    request<Proposal>(`/proposals/${id}`, { method: "PATCH", body: JSON.stringify({ amount }) }),
  permissions: () => request<Permission[]>("/permissions"),
  savePermission: (row: Permission) =>
    request<Permission>(`/permissions/${row.action_type}`, {
      method: "PATCH",
      body: JSON.stringify({
        tier: row.tier,
        per_action_limit: row.per_action_limit,
        daily_limit: row.daily_limit,
      }),
    }),
  audit: (outcome: string) => request<AuditRow[]>(`/audit${outcome ? `?policy_outcome=${outcome}` : ""}`),
  exportAudit: () => request<string>("/audit/export"),
  chat: (message: string) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message }) }),
  correct: (id: number, category: string) =>
    request<Txn>(`/transactions/${id}/category?user_id=1`, {
      method: "PATCH",
      body: JSON.stringify({ category }),
    }),
  simulate: (changes: { op: string; merchant?: string; category?: string; amount?: number }[]) =>
    request<Scenario>("/insights/simulate", { method: "POST", body: JSON.stringify({ changes }) }),
  recurring: () => request<{ recurring: { merchant: string; amount: number; frequency: string; next_due: string }[] }>(
    "/insights/recurring",
  ),
};

export function usd(value: number) {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export const CATEGORIES = [
  "income",
  "housing",
  "groceries",
  "transport",
  "subscriptions",
  "utilities",
  "education",
  "dining",
  "shopping",
  "savings",
  "other",
];
