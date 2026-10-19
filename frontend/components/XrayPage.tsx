"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { api, ApiError, type Quarter, type Xray } from '@/lib/api';
import { pct, ratio, upDownClass, yi } from '@/lib/format';
import { YoyChart } from '@/components/Charts';
import AiReading from '@/components/AiReading';
import CheckCard from '@/components/CheckCard';
import EarningsCalls from '@/components/EarningsCalls';
import QuickPicks from '@/components/QuickPicks';
import StockSearch from '@/components/StockSearch';
import { Card, ErrorBox, Loading, SourceNote } from '@/components/ui';

export default function XrayPage() {
  const ticker = useSearchParams().get('ticker')?.toUpperCase() ?? '';
  const [data, setData] = useState<Xray | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    setError('');
    api<Xray>(`/stocks/${ticker}/xray`)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, [ticker]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">營收 X 光</h2>
          <p className="text-sm text-slate-500">用月營收與季報數字檢查成長的含金量，每一項都附上計算依據</p>
        </div>
        <StockSearch basePath="/analysis" initial={ticker} />
      </header>

      {!ticker && <QuickPicks basePath="/analysis" intro="輸入股票代碼或名稱，檢查它的營收成長品質：" />}
      {ticker && error && <ErrorBox message={error} />}
      {ticker && !error && !data && <Loading text={`正在讀取 ${ticker} 的財報…`} />}
      {data && <XrayBody data={data} />}
    </div>
  );
}

function XrayBody({ data }: { data: Xray }) {
  const counts = data.checks.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.status]: (acc[c.status] ?? 0) + 1 }), {});
  return (
    <>
      <section className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm grid md:grid-cols-[auto_1fr] gap-6 items-center">
        <div className="text-center md:text-left md:pr-6 md:border-r border-slate-200">
          <div className="text-sm text-slate-500">
            <Link href={`/?ticker=${data.stock.stock_id}`} className="hover:text-indigo-600">
              {data.stock.name} {data.stock.stock_id}
            </Link>
          </div>
          <div className="text-5xl font-bold tabular-nums text-indigo-600 mt-1">{data.score ?? '—'}</div>
          <div className="font-medium mt-1">{data.grade}</div>
        </div>
        <div className="space-y-2 text-sm text-slate-600">
          <p>
            共 {data.checks.length} 項檢查：
            <span className="text-green-700">健康 {counts.good ?? 0}</span>、
            <span className="text-amber-700">留意 {counts.warn ?? 0}</span>、
            <span className="text-red-700">警訊 {counts.bad ?? 0}</span>
            {counts.na ? <>、<span className="text-slate-500">不適用 {counts.na}</span></> : null}。
          </p>
          <p className="text-xs text-slate-500">
            計分方式：從 100 分開始，每個「警訊」扣 20 分、每個「留意」扣 8 分；可評估的項目少於 4 項時不給分數。
            {data.score === null && ' 金融、保險等產業的財報格式不同，大部分檢查不適用。'}
          </p>
          <p className="text-xs text-slate-500">
            資料截至：月營收 {data.data_as_of.month ?? '—'}・季報 {data.data_as_of.quarter ?? '—'}
          </p>
        </div>
      </section>

      <div className="grid md:grid-cols-2 gap-3">
        {data.checks.map((c) => <CheckCard key={c.id} check={c} />)}
      </div>

      <AiReading
        endpoint={`/stocks/${data.stock.stock_id}/ai-report`}
        subtitle="Claude 只根據本頁的數字撰寫，不引用外部新聞；每檔股票每天產生一次"
        sections={[
          { key: 'growth_sources', title: '成長來源' },
          { key: 'risks', title: '風險與疑點', empty: '沒有發現明顯疑點。' },
          { key: 'watch_items', title: '接下來要追蹤' },
        ]}
      />

      <EarningsCalls ticker={data.stock.stock_id} />

      <Card title="月營收年增率" subtitle="近 24 個月（%）">
        <YoyChart data={data.monthly_revenue} />
      </Card>

      <Card title="季度財務數據" subtitle="單季數字，單位：億元；最新一季在最上面">
        <QuarterTable quarters={data.quarters} />
      </Card>

      <SourceNote>
        季報數字為合併報表單季值；營業現金流由累計數換算為單季。公司公告季報後約 1-2 天更新。
      </SourceNote>
    </>
  );
}

function QuarterTable({ quarters }: { quarters: Quarter[] }) {
  const rows = [...quarters].reverse().slice(0, 8);
  const byQuarter = Object.fromEntries(quarters.map((q) => [q.quarter, q]));
  const yearAgo = (q: Quarter) => byQuarter[`${Number(q.quarter.slice(0, 4)) - 1}${q.quarter.slice(4)}`];
  return (
    <div className="overflow-x-auto -mx-5 px-5">
      <table className="w-full text-sm tabular-nums min-w-[720px]">
        <thead className="text-xs text-slate-500 border-b">
          <tr className="text-right">
            <th className="text-left font-medium py-2">季度</th>
            <th className="font-medium">營收</th>
            <th className="font-medium">營收年增</th>
            <th className="font-medium">毛利率</th>
            <th className="font-medium">營益率</th>
            <th className="font-medium">業外占稅前</th>
            <th className="font-medium">稅後淨利</th>
            <th className="font-medium">營業現金流</th>
            <th className="font-medium">EPS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((q) => {
            const ago = yearAgo(q);
            const revYoy = ago && ago.revenue && q.revenue ? ((q.revenue - ago.revenue) / Math.abs(ago.revenue)) * 100 : null;
            return (
              <tr key={q.quarter} className="border-b last:border-0 text-right">
                <td className="text-left py-2 font-medium">{q.quarter}</td>
                <td>{yi(q.revenue)}</td>
                <td className={upDownClass(revYoy)}>{pct(revYoy)}</td>
                <td>{pct(ratio(q.gross_profit, q.revenue), 1, false)}</td>
                <td>{pct(ratio(q.operating_income, q.revenue), 1, false)}</td>
                <td>{q.pretax_income && q.pretax_income > 0 ? pct(ratio(q.non_operating, q.pretax_income), 1, false) : '—'}</td>
                <td>{yi(q.net_income)}</td>
                <td>{yi(q.operating_cash_flow)}</td>
                <td>{q.eps ?? '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
