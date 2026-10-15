import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Inbox,
  LineChart,
  Settings,
  ScrollText,
  Menu,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/inbox", label: "Approval Inbox", icon: Inbox },
  { to: "/simulator", label: "What-if", icon: LineChart },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/audit", label: "Audit Log", icon: ScrollText },
];

function NavItems({ pending, onNavigate }: { pending: number; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {links.map((link) => {
        const Icon = link.icon;
        return (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="flex-1">{link.label}</span>
            {link.to === "/inbox" && pending > 0 ? (
              <Badge variant="secondary" className="border-0">
                {pending}
              </Badge>
            ) : null}
          </NavLink>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <div>
      <p className="font-serif text-2xl tracking-tight text-primary">FinPilot</p>
      <p className="mt-1 text-xs text-muted-foreground">Student sandbox account</p>
    </div>
  );
}

export default function Layout() {
  const [pending, setPending] = useState(0);
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    api.proposals("pending").then((rows) => setPending(rows.length)).catch(() => setPending(0));
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background">
      <div
        className="flex items-center justify-center gap-2 border-b bg-secondary px-4 py-2 text-center text-xs text-secondary-foreground md:text-sm"
        role="status"
      >
        <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
        Sandbox — not real money, and not regulated financial advice.
      </div>

      <div className="mx-auto grid max-w-6xl gap-0 md:grid-cols-[220px_1fr]">
        <aside className="hidden border-r md:block">
          <div className="sticky top-0 space-y-6 p-5">
            <Brand />
            <Separator />
            <NavItems pending={pending} />
          </div>
        </aside>

        <div className="min-w-0">
          <div className="flex items-center gap-2 border-b px-4 py-3 md:hidden">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" aria-label="Open menu">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72">
                <SheetHeader className="mb-6">
                  <SheetTitle className="font-serif text-left text-primary">FinPilot</SheetTitle>
                </SheetHeader>
                <NavItems pending={pending} onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>
            <p className="font-serif text-lg text-primary">FinPilot</p>
            {pending > 0 ? <Badge className="ml-auto">{pending} pending</Badge> : null}
          </div>

          <main className="animate-in fade-in duration-300 p-4 md:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
