"use client";

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Plus } from 'lucide-react';
import { api, ApiError, jsonBody, type DecisionDetail, type DecisionSummary } from '@/lib/api';
import { dateTime } from '@/lib/format';
import { Badge, Card, ErrorBox, Loading } from '@/components/ui';

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<DecisionSummary[]>('/decisions')
      .then(setDecisions)
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold">投資決策</h2>
        <p className="text-sm text-slate-500">寫下買進理由，讓 AI 用真實財報數字挑戰你，並持續追蹤論點是否還成立</p>
      </header>

      <NewDecisionForm />

      <Card title="我的決策紀錄">
        {error && <ErrorBox message={error} />}
        {!error && !decisions && <Loading />}
        {decisions && decisions.length === 0 && (
          <p className="text-sm text-slate-500">還沒有任何決策。在上方寫下第一個投資論點。</p>
        )}
        {decisions && decisions.length > 0 && (
          <ul className="divide-y divide-slate-100 -my-2">
            {decisions.map((d) => <DecisionRow key={d.id} d={d} />)}
          </ul>
        )}
      </Card>
    </div>
  );
}

function DecisionRow({ d }: { d: DecisionSummary }) {
  const s = d.skeptic;
  return (
    <li>
      <Link href={`/decisions/${d.id}`} className="block py-3 group">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <span className="font-semibold group-hover:text-indigo-600">{d.stock_name} {d.ticker}</span>
          <span className="text-xs text-slate-500 tabular-nums">更新於 {dateTime(d.updated_at)}</span>
        </div>
        <p className="text-sm text-slate-600 mt-1 line-clamp-2">{d.thesis}</p>
        <div className="flex flex-wrap gap-2 mt-2 text-xs">
          <Badge>信心 {d.conviction}/10</Badge>
          <Badge>監控 {d.monitor_count} 項</Badge>
          {!s && <Badge>尚未接受 AI 質疑</Badge>}
          {s?.status === 'pending' && <Badge>AI 質疑產生中</Badge>}
          {s?.status === 'error' && <Badge cls="text-red-700 bg-red-50 border-red-200">AI 質疑產生失敗</Badge>}
          {s?.status === 'done' && (
            <Badge>AI 質疑：<span className="text-green-700">通過 {s.passed}</span>・<span className="text-red-700">未通過 {s.failed}</span>・未回答 {3 - s.passed - s.failed}</Badge>
          )}
        </div>
      </Link>
    </li>
  );
}

function NewDecisionForm() {
  const router = useRouter();
  const initialTicker = useSearchParams().get('ticker')?.toUpperCase() ?? '';
  const [ticker, setTicker] = useState(initialTicker);
  const [thesis, setThesis] = useState('');
  const [conviction, setConviction] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => setTicker(initialTicker), [initialTicker]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const d = await api<DecisionDetail>('/decisions', jsonBody('POST', { ticker: ticker.trim(), thesis, conviction }));
      router.push(`/decisions/${d.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '建立失敗');
      setBusy(false);
    }
  };

  return (
    <Card title="新增投資決策" subtitle="論點寫得越具體（例如「月營收年增維持 20% 以上」），AI 越能幫你設定監控條件">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid sm:grid-cols-[10rem_1fr] gap-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">股票代碼</span>
            <input value={ticker} onChange={(e) => setTicker(e.target.value)} required placeholder="例如 2330"
              className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">信心程度：<span className="tabular-nums text-indigo-600">{conviction}</span>/10</span>
            <input type="range" min={1} max={10} value={conviction} onChange={(e) => setConviction(Number(e.target.value))}
              className="mt-3 w-full accent-indigo-600" />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">投資論點</span>
          <textarea value={thesis} onChange={(e) => setThesis(e.target.value)} required minLength={10} maxLength={3000} rows={4}
            placeholder="為什麼現在要買？成長來源是什麼？什麼情況代表你看錯了？"
            className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </label>
        {error && <ErrorBox message={error} />}
        <button type="submit" disabled={busy}
          className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-60">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <Plus className="w-4 h-4" aria-hidden />}
          建立決策
        </button>
      </form>
    </Card>
  );
}
