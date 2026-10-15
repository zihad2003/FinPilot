import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const links = [
  ["/", "Dashboard"],
  ["/chat", "Chat"],
  ["/inbox", "Approval Inbox"],
  ["/simulator", "What-if"],
  ["/settings", "Settings"],
  ["/audit", "Audit Log"],
];

export default function Layout() {
  const [pending, setPending] = useState(0);
  const location = useLocation();

  useEffect(() => {
    api.proposals("pending").then((rows) => setPending(rows.length)).catch(() => setPending(0));
  }, [location.pathname]);

  return (
    <div className="min-h-screen">
      <div className="bg-ink px-4 py-2 text-center text-sm text-paper" role="status">
        Sandbox — not real money, and not regulated financial advice.
      </div>
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 md:grid-cols-[200px_1fr]">
        <aside>
          <p className="font-serif text-3xl text-pine">FinPilot</p>
          <p className="mt-1 text-sm text-ink/70">Student sandbox account</p>
          <nav className="mt-6 flex flex-col gap-1">
            {links.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-pine text-white" : "hover:bg-white"}`
                }
              >
                {label}
                {to === "/inbox" && pending > 0 ? ` (${pending})` : ""}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
