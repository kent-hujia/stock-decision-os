"use client";

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { api, ApiError, jsonBody, type PaperOverview, type Swing, type TradeDetail } from '@/lib/api';
import { ntd, price, shares as fmtShares } from '@/lib/format';
import { SWING_LABELS } from '@/components/CheckCard';
import StockSearch from '@/components/StockSearch';
import { Badge, Card, ErrorBox, Loading, Stat } from '@/components/ui';

const INPUT = 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';
const STATUS_CLS = {
  good: 'text-green-700 bg-green-50 border-green-200',
  warn: 'text-amber-700 bg-amber-50 border-amber-200',
  bad: 'text-red-700 bg-red-50 border-red-200',
  na: 'text-slate-500 bg-slate-50 border-slate-200',
};

export default function NewTradePage() {
  const ticker = useSearchParams().get('ticker')?.toUpperCase() ?? '';
  const [swing, setSwing] = useState<Swing | null>(null);
  const [overview, setOverview] = useState<PaperOverview | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker) return;
    setSwing(null);
    setError('');
    Promise.all([api<Swing>(`/stocks/${ticker}/swing`), api<PaperOverview>('/paper/account')])
      .then(([s, o]) => { setSwing(s); setOverview(o); })
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, [ticker]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <Link href="/trades" className="text-sm text-slate-500 hover:text-indigo-600">← 模擬交易</Link>
          <h2 className="text-2xl font-bold">建立交易計畫</h2>
          <p className="text-sm text-slate-500">先寫好理由、停損和目標，系統依風險上限算出可以買多少</p>
        </div>
        <StockSearch basePath="/trades/new" initial={ticker} />
      </header>
      {!ticker && <p className="text-sm text-slate-500">先在右上角輸入要交易的股票。</p>}
      {ticker && error && <ErrorBox message={error} />}
      {ticker && !error && !swing && <Loading text={`正在讀取 ${ticker} 的波段檢查…`} />}
      {swing && overview && !swing.defense && <ErrorBox message="這檔股票的股價資料不足，無法建立交易計畫。" />}
      {swing?.defense && overview && <PlanForm swing={swing} overview={overview} />}
    </div>
  );
}

function PlanForm({ swing, overview }: { swing: Swing; overview: PaperOverview }) {
  const router = useRouter();
  const d = swing.defense!;
  const acc = overview.account;
  const [thesis, setThesis] = useState('');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limit, setLimit] = useState(String(d.close));
  const [stop, setStop] = useState(String(d.suggested_stop));
  const [target, setTarget] = useState(String(d.suggested_target));
  const [qty, setQty] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const entry = orderType === 'limit' ? Number(limit) : d.close;
  const stopN = Number(stop);
  const targetN = Number(target);
  const perShare = entry - stopN;
  const maxByRisk = perShare > 0 ? Math.floor(acc.risk_budget / perShare) : 0;
  const maxByCash = entry > 0 ? Math.floor(acc.available / (entry * 1.03)) : 0;
  const maxShares = Math.max(0, Math.min(maxByRisk, maxByCash));
  const qtyN = qty === '' ? maxShares : Math.floor(Number(qty));

  const problems = useMemo(() => {
    const out: string[] = [];
    if (!(entry > 0)) out.push('請填寫限價。');
    if (stopN >= entry) out.push(`停損價必須低於進場參考價 ${price(entry)}。`);
    if (targetN <= entry) out.push(`目標價必須高於進場參考價 ${price(entry)}。`);
    if (qtyN > maxShares) out.push(`股數超過上限 ${maxShares.toLocaleString('zh-TW')} 股。`);
    if (qtyN <= 0) out.push('可買股數為 0：停損太遠或可用資金不足。');
    return out;
  }, [entry, stopN, targetN, qtyN, maxShares]);

  const rr = perShare > 0 ? (targetN - entry) / perShare : null;
  const bad = swing.checks.filter((c) => c.status === 'bad');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (problems.length) return;
    setBusy(true);
    setError('');
    try {
      const t = await api<TradeDetail>('/paper/trades', jsonBody('POST', {
        ticker: swing.stock.stock_id, thesis, order_type: orderType,
        limit_price: orderType === 'limit' ? Number(limit) : null,
        stop_price: stopN, target_price: targetN, shares: qtyN,
      }));
      router.push(`/trades/${t.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '建立失敗');
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <Card title={`${swing.stock.name} ${swing.stock.stock_id}`} subtitle={`${d.date} 收盤 ${price(d.close)}；下單後最快下一個交易日成交`}>
        <div className="flex flex-wrap gap-2 text-xs">
          {swing.checks.map((c) => (
            <Badge key={c.id} cls={STATUS_CLS[c.status]}>{c.title}：{c.status === 'na' ? '不適用' : SWING_LABELS[c.status]}</Badge>
          ))}
        </div>
        {bad.length > 0 && (
          <p className="text-sm text-red-700 mt-3">
            有 {bad.length} 項不利：{bad.map((c) => c.title).join('、')}。進場理由要能解釋為什麼可以忽略它們。
          </p>
        )}
        <Link href={`/swing?ticker=${swing.stock.stock_id}`} className="inline-block text-sm text-indigo-600 hover:text-indigo-800 mt-2">看完整波段檢查 →</Link>
      </Card>

      <Card title="進場理由" subtitle="為什麼是這檔、為什麼是現在、什麼情況代表看錯">
        <textarea value={thesis} onChange={(e) => setThesis(e.target.value)} required minLength={10} maxLength={2000} rows={4}
          placeholder="例如：站回 20 日均線且量增，投信連買 5 天；跌破近 20 日低點代表看錯。" aria-label="進場理由" className={`${INPUT} leading-relaxed`} />
      </Card>

      <Card title="價格與部位" subtitle={`每筆最多虧總資產的 ${acc.risk_pct}%（${ntd(acc.risk_budget)}）；可用資金 ${ntd(acc.available)}`}>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">進場方式</span>
            <select value={orderType} onChange={(e) => setOrderType(e.target.value as 'market' | 'limit')} className={`${INPUT} mt-1`}>
              <option value="market">下一個交易日開盤市價</option>
              <option value="limit">限價（5 個交易日內有效）</option>
            </select>
          </label>
          {orderType === 'limit' && (
            <label className="block">
              <span className="text-sm font-medium text-slate-700">限價</span>
              <input type="number" step="any" min="0" value={limit} onChange={(e) => setLimit(e.target.value)} className={`${INPUT} mt-1`} />
            </label>
          )}
          <label className="block">
            <span className="text-sm font-medium text-slate-700">停損價</span>
            <input type="number" step="any" min="0" value={stop} onChange={(e) => setStop(e.target.value)} className={`${INPUT} mt-1`} />
            <span className="text-xs text-slate-500">建議 {price(d.suggested_stop)}（{d.stop_basis}）</span>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">目標價</span>
            <input type="number" step="any" min="0" value={target} onChange={(e) => setTarget(e.target.value)} className={`${INPUT} mt-1`} />
            <span className="text-xs text-slate-500">近 20 日高點 {price(d.high20)}</span>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">股數</span>
            <input type="number" min="1" step="1" value={qty} onChange={(e) => setQty(e.target.value)}
              placeholder={String(maxShares)} className={`${INPUT} mt-1`} />
            <span className="text-xs text-slate-500">留空 = 上限 {fmtShares(maxShares)}</span>
          </label>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="部位金額" value={ntd(entry * qtyN)} sub={fmtShares(Math.max(0, qtyN))} />
          <Stat label="最多虧損" value={ntd(perShare * qtyN)} valueClass="text-green-700"
            sub={`每股 ${price(perShare)}（${((perShare / entry) * 100).toFixed(1)}%）`} />
          <Stat label="目標獲利" value={ntd((targetN - entry) * qtyN)} valueClass="text-red-600"
            sub={`每股 ${price(targetN - entry)}`} />
          <Stat label="報酬風險比" value={rr === null ? '—' : `${rr.toFixed(2)} 倍`}
            sub={rr !== null && rr < 1.5 ? '低於 1.5 倍，勝率要很高才划算' : '賺的幅度是可能虧的幾倍'} />
        </div>
        <p className="text-xs text-slate-500 mt-3">
          股數上限取「風險上限 ÷ 每股風險」與「可用資金 ÷（進場價 × 1.03）」較小者；可以買零股。
          成交會扣手續費 0.1425%（最低 20 元），賣出另扣證交稅 0.3%。
        </p>
      </Card>

      {problems.length > 0 && <ErrorBox message={problems.join(' ')} />}
      {error && <ErrorBox message={error} />}
      <button type="submit" disabled={busy || problems.length > 0}
        className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50">
        {busy && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}送出委託
      </button>
    </form>
  );
}
