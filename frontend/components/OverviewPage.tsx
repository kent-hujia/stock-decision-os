"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { api, ApiError, type Overview } from '@/lib/api';
import { lots, pct, upDownClass, yi } from '@/lib/format';
import { InstitutionalChart, PriceChart, RevenueChart, YoyChart } from '@/components/Charts';
import QuickPicks from '@/components/QuickPicks';
import StockSearch from '@/components/StockSearch';
import { Card, ErrorBox, Loading, SourceNote, Stat } from '@/components/ui';

const RANGES = [
  { label: '1月', days: 22 },
  { label: '3月', days: 66 },
  { label: '6月', days: 130 },
  { label: '1年', days: 250 },
];

export default function OverviewPage() {
  const ticker = useSearchParams().get('ticker')?.toUpperCase() ?? '';
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');
  const [range, setRange] = useState(130);

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    setError('');
    api<Overview>(`/stocks/${ticker}/overview`)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, [ticker]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">個股總覽</h2>
          <p className="text-sm text-slate-500">股價、三大法人籌碼與月營收，全部來自公開交易與申報資料</p>
        </div>
        <StockSearch basePath="/" initial={ticker} />
      </header>

      {!ticker && <QuickPicks basePath="/" intro="輸入股票代碼或名稱開始，或從這幾檔看起：" />}
      {ticker && error && <ErrorBox message={error} />}
      {ticker && !error && !data && <Loading text={`正在讀取 ${ticker} 的資料…`} />}
      {data && <OverviewBody data={data} range={range} setRange={setRange} />}
    </div>
  );
}

function OverviewBody({ data, range, setRange }: {
  data: Overview;
  range: number;
  setRange: (d: number) => void;
}) {
  const { stock, latest, revenue_summary: rev, institutional_sums: sums } = data;
  return (
    <>
      <section className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="text-2xl font-bold">{stock.name}</h3>
            <span className="font-mono text-slate-500">{stock.stock_id}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">{stock.market}</span>
            {stock.industries.map((i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">{i}</span>
            ))}
          </div>
          {latest && (
            <div className="flex items-baseline gap-3 mt-2">
              <span className="text-3xl font-semibold tabular-nums">{latest.close.toLocaleString('zh-TW')}</span>
              <span className={`tabular-nums font-medium ${upDownClass(latest.change)}`}>
                {latest.change !== null && `${latest.change > 0 ? '+' : ''}${latest.change}`}（{pct(latest.change_pct, 2)}）
              </span>
              <span className="text-xs text-slate-500">{latest.date} 收盤</span>
            </div>
          )}
        </div>
        <Link href={`/analysis?ticker=${stock.stock_id}`}
          className="inline-flex items-center gap-2 self-start md:self-center bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700">
          營收 X 光分析 <ArrowRight className="w-4 h-4" aria-hidden />
        </Link>
      </section>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label={rev ? `${rev.period} 月營收` : '月營收'} value={rev ? yi(rev.revenue) : '—'}
          sub={rev && <>年增 <span className={upDownClass(rev.yoy)}>{pct(rev.yoy)}</span>・月增 <span className={upDownClass(rev.mom)}>{pct(rev.mom)}</span></>} />
        <Stat label="今年累計營收" value={rev ? yi(rev.ytd_revenue, 0) : '—'}
          sub={rev && <>年增 <span className={upDownClass(rev.ytd_yoy)}>{pct(rev.ytd_yoy)}</span></>} />
        <Stat label="外資近 5 日" value={lots(sums.foreign_5d ?? 0)} valueClass={upDownClass(sums.foreign_5d)}
          sub={`近 20 日 ${lots(sums.foreign_20d ?? 0)}`} />
        <Stat label="投信近 5 日" value={lots(sums.trust_5d ?? 0)} valueClass={upDownClass(sums.trust_5d)}
          sub={`近 20 日 ${lots(sums.trust_20d ?? 0)}`} />
      </div>

      <Card
        title="股價走勢"
        subtitle={latest ? `52 週區間 ${latest.low_52w.toLocaleString('zh-TW')} – ${latest.high_52w.toLocaleString('zh-TW')}` : undefined}
        action={
          <div className="flex gap-1" role="group" aria-label="時間範圍">
            {RANGES.map((r) => (
              <button key={r.days} onClick={() => setRange(r.days)} aria-pressed={range === r.days}
                className={`whitespace-nowrap text-xs px-2.5 py-1 rounded-md border ${range === r.days ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-300 text-slate-600 hover:border-indigo-400'}`}>
                {r.label}
              </button>
            ))}
          </div>
        }
      >
        {data.prices.length ? <PriceChart data={data.prices.slice(-range)} /> : <p className="text-sm text-slate-500">沒有股價資料。</p>}
      </Card>

      <Card title="三大法人買賣超" subtitle="近 20 個交易日，單位：張（正值為買超）">
        {data.institutional.length
          ? <InstitutionalChart data={data.institutional} />
          : <p className="text-sm text-slate-500">沒有法人買賣資料。</p>}
      </Card>

      <Card title="月營收" subtitle="近 24 個月，單位：億元">
        {data.monthly_revenue.length ? (
          <div className="space-y-2">
            <RevenueChart data={data.monthly_revenue} />
            <div>
              <h4 className="text-xs font-medium text-slate-500 mb-1">年增率（%）</h4>
              <YoyChart data={data.monthly_revenue} />
            </div>
          </div>
        ) : <p className="text-sm text-slate-500">沒有月營收資料。</p>}
      </Card>

      <SourceNote>股價與法人資料每個交易日盤後更新；月營收於每月 10 日前公布上月數字。</SourceNote>
    </>
  );
}
