"use client";

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

const LINKS = [
  { href: '/', label: '個股總覽' },
  { href: '/analysis', label: '營收 X 光' },
  { href: '/decisions', label: '投資決策' },
];

export default function Nav() {
  const pathname = usePathname();
  const ticker = useSearchParams().get('ticker');
  const query = ticker ? `?ticker=${encodeURIComponent(ticker)}` : '';
  return (
    <div className="flex gap-1 text-sm font-medium">
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={`${l.href}${query}`}
          className={`px-3 py-1.5 rounded-md transition ${(l.href === '/' ? pathname === '/' : pathname.startsWith(l.href)) ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:text-indigo-600'}`}
        >
          {l.label}
        </Link>
      ))}
    </div>
  );
}
