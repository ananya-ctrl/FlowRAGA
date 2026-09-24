"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Projects" },
];

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function AppShell({
  userName,
  onSignOut,
  topbar,
  children,
}: Readonly<{
  userName: string;
  onSignOut: () => void;
  topbar?: ReactNode;
  children: ReactNode;
}>) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link className="brand" href="/dashboard">FlowRAGA</Link>

        <nav className="sidebar-nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname?.startsWith(item.href) ? "active" : ""}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">{initials(userName)}</span>
            <span>{userName}</span>
          </div>
          <button className="quiet-button" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">{topbar}</header>
        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}
