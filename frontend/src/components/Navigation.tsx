"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Cpu,
  Menu,
  X,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/optimizer", label: "Optimizer", icon: Cpu },
];

export default function Navigation() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [prevPathname, setPrevPathname] = useState(pathname);

  // Close drawer on route change (React docs pattern: "Adjusting state when a prop changes")
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setMobileOpen(false);
  }

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--card)]/95 backdrop-blur supports-[backdrop-filter]:bg-[var(--card)]/60">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
              <span className="text-sm font-black text-[var(--primary-foreground)]">
                FPL
              </span>
            </div>
            <span className="text-lg font-bold fpl-gradient-text hidden sm:inline">
              FPL Picker
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50 hover:text-[var(--foreground)]"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Mobile hamburger button */}
          <button
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]/50 transition-colors"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </header>

      {/* Mobile slide-out drawer overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm md:hidden animate-fade-in"
          onClick={closeMobile}
        />
      )}

      {/* Mobile slide-out drawer */}
      <div
        className={`fixed top-0 right-0 z-[70] h-full w-72 max-w-[80vw] border-l border-[var(--border)] bg-[var(--card)] shadow-2xl md:hidden transition-transform duration-300 ease-out ${
          mobileOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <span className="text-lg font-bold fpl-gradient-text">Menu</span>
          <button
            onClick={closeMobile}
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[var(--muted)] transition-colors"
          >
            <X className="h-5 w-5 text-[var(--muted-foreground)]" />
          </button>
        </div>

        {/* Drawer nav items */}
        <nav className="px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={closeMobile}
                className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-[var(--primary)]/10 text-[var(--primary)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50 hover:text-[var(--foreground)]"
                }`}
              >
                <Icon className="h-5 w-5" />
                {item.label}
                {isActive && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-[var(--primary)]" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Drawer footer */}
        <div className="absolute bottom-0 left-0 right-0 border-t border-[var(--border)] px-5 py-4">
          <p className="text-xs text-[var(--muted-foreground)]">
            FPL Team Picker
          </p>
        </div>
      </div>
    </>
  );
}
