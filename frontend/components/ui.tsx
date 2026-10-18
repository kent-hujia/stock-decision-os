import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

export function Card({ title, subtitle, action, children }: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
      {(title || action) && (
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 mb-4">
          <div>
            {title && <h3 className="font-semibold text-slate-900">{title}</h3>}
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, valueClass = '' }: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-xl font-semibold tabular-nums mt-1 ${valueClass}`}>{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5 tabular-nums">{sub}</div>}
    </div>
  );
}

export function Loading({ text = '載入中…' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-24 text-slate-500">
      <Loader2 className="w-5 h-5 animate-spin" aria-hidden />
      {text}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 border border-red-200 bg-red-50 text-red-700 rounded-xl px-4 py-3 text-sm">
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
      {message}
    </div>
  );
}

export function SourceNote({ children }: { children: ReactNode }) {
  return <p className="text-xs text-slate-400">{children}</p>;
}

export function Badge({ children, cls = 'text-slate-600 bg-slate-50 border-slate-200' }: {
  children: ReactNode;
  cls?: string;
}) {
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${cls}`}>{children}</span>;
}
