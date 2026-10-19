"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ClipboardList } from 'lucide-react';
import { api, ApiError, type ChipPoint, type Defense, type Swing } from '@/lib/api';
import { lots, pct, price } from '@/lib/format';
import { InstitutionalChart, SwingPriceChart } from '@/components/Charts';
import AiReading from '@/components/AiReading';
import CheckCard, { SWING_LABELS } from '@/components/CheckCard';
import QuickPicks from '@/components/QuickPicks';
import StockSearch from '@/components/StockSearch';
import { Card, ErrorBox, Loading, SourceNote, Stat } from '@/components/ui';

export default function SwingPage() {
  const ticker = useSearchParams().get('ticker')?.toUpperCase() ?? '';
  const [data, setData] = useState<Swing | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    setError('');
    api<Swing>(`/stocks/${ticker}/swing`)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, [ticker]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">波段檢查</h2>
          <p className="text-sm text-slate-500">進場前逐項確認趨勢、量能、主力與散戶籌碼，並找出技術防守點</p>
        </div>
        <StockSearch basePath="/swing" initial={ticker} />
      </header>

      {!ticker && <QuickPicks basePath="/swing" intro="輸入股票代碼或名稱，檢查它現在適不適合做波段：" />}
      {ticker && error && <ErrorBox message={error} />}
      {ticker && !error && !data && <Loading text={`正在讀取 ${ticker} 的股價與籌碼…`} />}
      {data && <SwingBody data={data} />}
    </div>
  );
}

function SwingBody({ data }: { data: Swing }) {
  const counts = data.checks.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.status]: (acc[c.status] ?? 0) + 1 }), {});
  const id = data.stock.stock_id;
  return (
    <>
      <section className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm text-slate-500">
            <Link href={`/?ticker=${id}`} className="hover:text-indigo-600">{data.stock.name} {id}</Link>
            ・資料截至 {data.data_as_of.price ?? '—'}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            共 {data.checks.length} 項：
            <span className="text-green-700">有利 {counts.good ?? 0}</span>、
            <span className="text-amber-700">留意 {counts.warn ?? 0}</span>、
            <span className="text-red-700">不利 {counts.bad ?? 0}</span>
            {counts.na ? <>、<span className="text-slate-500">不適用 {counts.na}</span></> : null}。
            沒有總分：每一項都要自己判斷是否和進場理由衝突。
          </p>
        </div>
        <Link href={`/trades/new?ticker=${id}`}
          className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700">
          <ClipboardList className="w-4 h-4" aria-hidden />建立交易計畫
        </Link>
      </section>

      <div className="grid md:grid-cols-2 gap-3">
        {data.checks.map((c) => <CheckCard key={c.id} check={c} labels={SWING_LABELS} />)}
      </div>

      {data.defense && <DefenseCard d={data.defense} />}

      <Card title="股價與均線" subtitle="近 120 個交易日；虛線為建議的停損與目標價">
        <SwingPriceChart data={data.prices} stop={data.defense?.suggested_stop} target={data.defense?.suggested_target} />
      </Card>

      <AiReading
        endpoint={`/stocks/${id}/swing-reading`}
        title="AI 籌碼解讀"
        subtitle="Claude（較便宜的 Haiku 模型）只根據本頁的技術面與籌碼數字解讀；每檔股票每天產生一次"
        pendingText="Claude 正在解讀籌碼與技術面，通常 30 秒內完成…"
        sections={[
          { key: 'chips', title: '主力與散戶籌碼' },
          { key: 'technical', title: '技術面' },
          { key: 'watch_items', title: '接下來盯什麼' },
        ]}
      />

      <Card title="法人買賣超" subtitle="近 20 個交易日（張）">
        <InstitutionalChart data={data.institutional} />
      </Card>

      <Card title="籌碼明細" subtitle="近 10 個交易日；單位：張（外資持股與當沖比為 %）">
        <ChipTable chips={data.chips.slice(-10).reverse()} />
      </Card>

      <SourceNote>
        股價、法人、融資融券、借券賣出、外資持股、當沖資料來自 FinMind（證交所、櫃買中心）。
        融資融券約在晚上 9 點半後更新。千張大戶與券商分點資料需付費，目前未納入。
      </SourceNote>
    </>
  );
}

function DefenseCard({ d }: { d: Defense }) {
  return (
    <Card title="技術防守點" subtitle={`以 ${d.date} 收盤 ${price(d.close)} 計算；建立交易計畫時會自動帶入，可以自己調整`}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="建議停損" value={price(d.suggested_stop)} sub={`${d.stop_basis}・距收盤 -${d.stop_distance_pct}%`} valueClass="text-green-700" />
        <Stat label="建議目標（2 倍風險）" value={price(d.suggested_target)} sub={`距收盤 ${pct((d.suggested_target / d.close - 1) * 100)}`} valueClass="text-red-600" />
        <Stat label="近 20 日高點" value={price(d.high20)} sub={`近 60 日高點 ${price(d.high60)}`} />
        <Stat label="均線" value={price(d.ma20)} sub={`20 日；60 日 ${price(d.ma60)}`} />
      </div>
      <p className="text-xs text-slate-500 mt-3">
        停損取收盤價下方 2% 以外最近的支撐（近 10／20／60 日低點、20／60 日均線），再往下一檔。
        近期高點是常見的壓力位，目標價超過壓力位時要有更強的理由。
      </p>
    </Card>
  );
}

function ChipTable({ chips }: { chips: ChipPoint[] }) {
  return (
    <div className="overflow-x-auto -mx-5 px-5">
      <table className="w-full text-sm tabular-nums min-w-[560px]">
        <thead className="text-xs text-slate-500 border-b">
          <tr className="text-right">
            <th className="text-left font-medium py-2">日期</th>
            <th className="font-medium">融資餘額</th>
            <th className="font-medium">融券餘額</th>
            <th className="font-medium">借券賣出餘額</th>
            <th className="font-medium">外資持股</th>
            <th className="font-medium">當沖比</th>
          </tr>
        </thead>
        <tbody>
          {chips.map((c, i) => {
            const prev = chips[i + 1];
            const diff = prev ? c.margin_balance - prev.margin_balance : null;
            return (
              <tr key={c.date} className="text-right border-b border-slate-100 last:border-0">
                <td className="text-left py-2">{c.date.slice(5)}</td>
                <td>{c.margin_balance.toLocaleString('zh-TW')}{diff !== null && <span className="text-xs text-slate-400 ml-1">{lots(diff).replace(' 張', '')}</span>}</td>
                <td>{c.short_balance.toLocaleString('zh-TW')}</td>
                <td>{c.sbl_balance === null ? '—' : c.sbl_balance.toLocaleString('zh-TW')}</td>
                <td>{c.foreign_ratio === null ? '—' : `${c.foreign_ratio.toFixed(2)}%`}</td>
                <td>{c.day_trade_ratio === null ? '—' : `${c.day_trade_ratio.toFixed(1)}%`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
