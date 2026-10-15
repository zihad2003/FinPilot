import { cn } from "@/lib/utils";

export function Money({ value, className }: { value: number; className?: string }) {
  const formatted = value.toLocaleString("en-US", { style: "currency", currency: "USD" });
  return <span className={cn("num", className)}>{formatted}</span>;
}
