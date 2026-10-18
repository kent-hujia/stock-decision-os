"use client";

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { api } from '@/lib/api';

interface Suggestion {
  stock_id: string;
  name: string;
}

const CODE_RE = /^[0-9]{4,6}[A-Za-z]?$/;

export default function StockSearch({ basePath, initial = '' }: { basePath: string; initial?: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initial);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => setQuery(initial), [initial]);

  useEffect(() => {
    const q = query.trim();
    if (!q || q === initial) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      api<Suggestion[]>(`/stocks/search?q=${encodeURIComponent(q)}`)
        .then((s) => {
          setSuggestions(s);
          setActive(0);
          setOpen(true);
        })
        .catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, initial]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const go = (ticker: string) => {
    setOpen(false);
    router.push(`${basePath}?ticker=${encodeURIComponent(ticker.toUpperCase())}`);
  };

  const submit = () => {
    const q = query.trim();
    if (open && suggestions[active]) return go(suggestions[active].stock_id);
    if (CODE_RE.test(q)) return go(q);
    if (suggestions[0]) return go(suggestions[0].stock_id);
  };

  return (
    <div ref={boxRef} className="relative w-full sm:w-80">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" aria-hidden />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => suggestions.length && setOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, suggestions.length - 1));
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === 'Escape') {
                setOpen(false);
              }
            }}
            placeholder="股票代碼或名稱，例如 2330、台積電"
            aria-label="搜尋股票"
            className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 outline-none"
          />
        </div>
        <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition">
          查詢
        </button>
      </form>
      {open && suggestions.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-72 overflow-auto">
          {suggestions.map((s, i) => (
            <li key={s.stock_id}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(s.stock_id)}
                onMouseEnter={() => setActive(i)}
                className={`w-full text-left px-3 py-2 text-sm flex gap-3 ${i === active ? 'bg-indigo-50' : ''}`}
              >
                <span className="font-mono text-slate-500 w-14">{s.stock_id}</span>
                <span>{s.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
