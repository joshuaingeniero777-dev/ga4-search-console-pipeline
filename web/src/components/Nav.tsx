"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const PAGES = [
  { href: "/", label: "Status" },
  { href: "/runs", label: "Run history" },
  { href: "/run-now", label: "Run now" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main">
      <ul>
        {PAGES.map((page) => (
          <li key={page.href}>
            <Link href={page.href} aria-current={pathname === page.href ? "page" : undefined}>
              {page.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
