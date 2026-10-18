"use client";

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { api, ApiError, type AiReport } from '@/lib/api';
import { Card, ErrorBox } from '@/components/ui';

const POLL_MS = 4000;

export default function AiReading({ ticker }: { ticker: string }) {
  const [report, setReport] = useState<AiReport | null>(null);
  const [error, setError] = useState('');

  const load = useCallback((method: 'GET' | 'POST') => {
    setError('');
    return api<AiReport>(`/stocks/${ticker}/ai-report`, { method })
      .then(setReport)
      .catch((e) => setError(e instanceof ApiError ? e.message : '讀取失敗'));
  }, [ticker]);

  useEffect(() => {
    setReport(null);
    load('GET');
  }, [load]);

  useEffect(() => {
    if (report?.status !== 'pending') return;
    const timer = setTimeout(() => load('GET'), POLL_MS);
    return () => clearTimeout(timer);
  }, [report, load]);

  const status = report?.status;
  const content = report?.content;

  return (
    <Card
      title="AI 解讀"
      subtitle="Claude 只根據本頁的數字撰寫，不引用外部新聞；每檔股票每天產生一次"
      action={(status === 'none' || status === 'error') && (
        <button onClick={() => load('POST')}
          className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700">
          <Sparkles className="w-4 h-4" aria-hidden />
          {status === 'error' ? '重新產生' : '產生 AI 解讀'}
        </button>
      )}
    >
      {error && <ErrorBox message={error} />}
      {!report && !error && <p className="text-sm text-slate-500">讀取中…</p>}
      {status === 'none' && <p className="text-sm text-slate-500">今天還沒有產生解讀。按右上角按鈕，大約需要 1 分鐘。</p>}
      {status === 'pending' && (
        <p className="flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
          Claude 正在閱讀財報數字，大約需要 1 分鐘，完成後會自動顯示…
        </p>
      )}
      {status === 'error' && <ErrorBox message={`產生失敗：${report?.error ?? '未知錯誤'}`} />}
      {status === 'done' && content && (
        <div className="space-y-4">
          <p className="text-base font-medium text-slate-900">{content.headline}</p>
          <ReadingList title="成長來源" items={content.growth_sources} />
          <ReadingList title="風險與疑點" items={content.risks} empty="沒有發現明顯疑點。" />
          <ReadingList title="接下來要追蹤" items={content.watch_items} />
          <p className="text-xs text-slate-400">產生日期 {report?.report_date}・不構成投資建議</p>
        </div>
      )}
    </Card>
  );
}

function ReadingList({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-700 mb-1">{title}</h4>
      {items.length ? (
        <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700 leading-relaxed">
          {items.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      ) : <p className="text-sm text-slate-500">{empty}</p>}
    </div>
  );
}
