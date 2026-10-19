"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Upload } from 'lucide-react';
import { api, ApiError, type EarningsCall } from '@/lib/api';
import { dateTime } from '@/lib/format';
import { Card, ErrorBox } from '@/components/ui';

const POLL_MS = 5000;

/** Upload an earnings-call (法說會) PDF and see Claude's breakdown of where revenue comes from. */
export default function EarningsCalls({ ticker }: { ticker: string }) {
  const [calls, setCalls] = useState<EarningsCall[] | null>(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<EarningsCall[]>(`/stocks/${ticker}/earnings-calls`)
    .then(setCalls).catch((e) => setError(e instanceof ApiError ? e.message : '讀取失敗')), [ticker]);
  useEffect(() => { setCalls(null); load(); }, [load]);
  useEffect(() => {
    if (!calls?.some((c) => c.status === 'pending')) return;
    const timer = setTimeout(load, POLL_MS);
    return () => clearTimeout(timer);
  }, [calls, load]);

  const upload = async (file: File) => {
    setError('');
    setUploading(true);
    const body = new FormData();
    body.append('file', file);
    try {
      await api(`/stocks/${ticker}/earnings-calls`, { method: 'POST', body });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '上傳失敗');
    } finally {
      setUploading(false);
      if (input.current) input.current.value = '';
    }
  };
  const act = async (path: string, method: string) => {
    setError('');
    try {
      await api(`/stocks/${ticker}/earnings-calls/${path}`, { method });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '操作失敗');
    }
  };

  return (
    <Card title="法說會拆解" subtitle="上傳公司法說會簡報 PDF（公開資訊觀測站或公司官網下載），Claude（Sonnet）拆解營收組成並和申報數字交叉核對；每份約 US$0.1–0.3"
      action={(
        <label className={`inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 cursor-pointer ${uploading ? 'opacity-60 pointer-events-none' : ''}`}>
          {uploading ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> : <Upload className="w-4 h-4" aria-hidden />}
          上傳 PDF
          <input ref={input} type="file" accept="application/pdf" className="sr-only"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
      )}>
      <div className="space-y-4">
        {error && <ErrorBox message={error} />}
        {calls && !calls.length && <p className="text-sm text-slate-500">還沒有上傳過這家公司的法說會簡報。不是每家公司都會開法說會。</p>}
        {calls?.map((c) => <CallItem key={c.id} c={c} onRetry={() => act(`${c.id}/retry`, 'POST')}
          onDelete={() => confirm(`刪除「${c.filename}」？`) && act(`${c.id}`, 'DELETE')} />)}
      </div>
    </Card>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-700 mb-1">{title}</h4>
      <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700 leading-relaxed">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

function CallItem({ c, onRetry, onDelete }: { c: EarningsCall; onRetry: () => void; onDelete: () => void }) {
  const k = c.content;
  return (
    <article className="border border-slate-200 rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>{c.filename}・{(c.size / 1024 / 1024).toFixed(1)} MB・{dateTime(c.created_at)}</span>
        <span className="flex gap-3">
          {c.status === 'error' && <button onClick={onRetry} className="text-indigo-600 hover:text-indigo-800">重新分析</button>}
          <button onClick={onDelete} className="hover:text-red-600">刪除</button>
        </span>
      </div>
      {c.status === 'pending' && <p className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="w-4 h-4 animate-spin" aria-hidden />Claude 正在閱讀簡報，大約需要 1-2 分鐘…</p>}
      {c.status === 'error' && <ErrorBox message={`分析失敗：${c.error ?? '未知錯誤'}`} />}
      {c.status === 'done' && k && <>
        <p className="font-medium text-slate-900"><span className="text-indigo-600 mr-2">{k.period}</span>{k.headline}</p>
        {k.segments.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead className="text-xs text-slate-500 border-b">
                <tr><th className="text-left font-medium py-1.5">類別</th><th className="text-right font-medium">占比</th><th className="text-left font-medium pl-4">趨勢</th><th className="text-left font-medium pl-4">說明</th></tr>
              </thead>
              <tbody>
                {k.segments.map((s, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0 align-top">
                    <td className="py-1.5 font-medium">{s.name}</td>
                    <td className="text-right tabular-nums">{s.share_pct === null ? '—' : `${s.share_pct}%`}</td>
                    <td className="pl-4">{s.trend}</td>
                    <td className="pl-4 text-slate-600">{s.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <List title="成長來源" items={k.growth_drivers} />
        <List title="一次性因素" items={k.one_off_items} />
        <List title="公司展望" items={k.guidance} />
        <List title="風險" items={k.risks} />
        <List title="與申報數字核對" items={k.consistency} />
        <p className="text-xs text-slate-400">簡報是公司自己的說法；占比與展望以簡報為準，未經查證。</p>
      </>}
    </article>
  );
}
