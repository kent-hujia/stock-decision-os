import { AlertTriangle, CheckCircle2, CircleSlash, XCircle } from 'lucide-react';
import type { Check, CheckStatus } from '@/lib/api';

export const STATUS: Record<CheckStatus, { label: string; icon: typeof CheckCircle2; cls: string }> = {
  good: { label: '健康', icon: CheckCircle2, cls: 'text-green-700 bg-green-50 border-green-200' },
  warn: { label: '留意', icon: AlertTriangle, cls: 'text-amber-700 bg-amber-50 border-amber-200' },
  bad: { label: '警訊', icon: XCircle, cls: 'text-red-700 bg-red-50 border-red-200' },
  na: { label: '不適用', icon: CircleSlash, cls: 'text-slate-500 bg-slate-50 border-slate-200' },
};

/** Swing checks judge fit for a long trade rather than health. */
export const SWING_LABELS = { good: '有利', warn: '留意', bad: '不利' } as const;

export default function CheckCard({ check, labels }: { check: Check; labels?: Partial<Record<CheckStatus, string>> }) {
  const s = STATUS[check.status];
  const Icon = s.icon;
  return (
    <article className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-semibold">{check.title}</h4>
        <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${s.cls}`}>
          <Icon className="w-3.5 h-3.5" aria-hidden />
          {labels?.[check.status] ?? s.label}
        </span>
      </div>
      <div className="text-lg font-semibold tabular-nums mt-1">{check.value}</div>
      <p className="text-sm text-slate-600 mt-1 leading-relaxed">{check.detail}</p>
    </article>
  );
}

