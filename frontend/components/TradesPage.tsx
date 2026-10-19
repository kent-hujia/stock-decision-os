"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Mail, Plus } from 'lucide-react';
import { api, ApiError, type NotifyStatus, type PaperOverview, type TradeStatus, type TradeSummary } from '@/lib/api';
import { dateTime, ntd, pct, price, shares, upDownClass } from '@/lib/format';
import { EquityChart } from '@/components/Charts';
import { Badge, Card, ErrorBox, Loading, SourceNote, Stat } from '@/components/ui';

export const TRADE_STATUS: Record<TradeStatus, { label: string; cls: string }> = {
  planned: { label: '委託中', cls: 'text-indigo-700 bg-indigo-50 border-indigo-200' },
  open: { label: '持有中', cls: 'text-amber-700 bg-amber-50 border-amber-200' },
  closed: { label: '已結束', cls: 'text-slate-700 bg-slate-100 border-slate-200' },
  cancelled: { label: '已取消', cls: 'text-slate-500 bg-slate-50 border-slate-200' },
};
export const EXIT_REASON = { stop: '停損出場', target: '達標出場', manual: '手動出場' };

export default function TradesPage() {
  const [data, setData] = useState<PaperOverview | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<PaperOverview>('/paper/account')
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : '載入失敗'));
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">模擬交易</h2>
          <p className="text-sm text-slate-500">虛擬資金、真實股價的波段練習帳戶；每筆都要有計畫、停損，結束後要檢討</p>
        </div>
        <Link href="/swing" className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 self-start">
          <Plus className="w-4 h-4" aria-hidden />從波段檢查開始
        </Link>
      </header>
      {error && <ErrorBox message={error} />}
      {!error && !data && <Loading text="正在更新模擬成交…" />}
      {data && <Body data={data} />}
    </div>
  );
}

function Body({ data }: { data: PaperOverview }) {
  const { account: a, stats: s } = data;
  const by = (st: TradeStatus) => data.trades.filter((t) => t.status === st);
  const closed = by('closed');
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="總資產" value={ntd(a.equity)} sub={`初始 ${ntd(a.initial_cash)}`} />
        <Stat label="報酬率" value={pct(a.return_pct, 2)} valueClass={upDownClass(a.return_pct)} sub={`已實現 ${ntd(s.realized_pnl, true)}`} />
        <Stat label="現金" value={ntd(a.cash)} sub={`委託預留 ${ntd(a.reserved)}`} />
        <Stat label="每筆風險上限" value={ntd(a.risk_budget)} sub={`總資產的 ${a.risk_pct}%`} />
      </div>

      {s.unreviewed > 0 && (
        <p className="text-sm bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3">
          有 {s.unreviewed} 筆已結束的交易還沒檢討。檢討才是練習的重點，點進交易填寫。
        </p>
      )}

      <TradeList title="持有中" trades={by('open')} empty="目前沒有持倉。" />
      <TradeList title="委託中" trades={by('planned')} empty="沒有等待成交的委託。" />
      <Card title="交易成績" subtitle="只計算已結束的交易；R = 損益 ÷ 進場時設定的最大虧損">
        {s.closed === 0 ? (
          <p className="text-sm text-slate-500">還沒有結束的交易。至少累積 20 筆，數字才開始有參考價值。</p>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="勝率" value={s.win_rate === null ? '—' : `${s.win_rate}%`} sub={`${s.closed} 筆已結束`} />
              <Stat label="平均 R" value={s.avg_r === null ? '—' : `${s.avg_r > 0 ? '+' : ''}${s.avg_r}R`}
                valueClass={upDownClass(s.avg_r)} sub="大於 0 代表長期有正期望值" />
              <Stat label="平均賺／賠" value={`${ntd(s.avg_win)} / ${ntd(s.avg_loss)}`}
                sub={s.profit_factor === null ? '獲利因子 —' : `獲利因子 ${s.profit_factor}`} />
              <Stat label="最大回撤" value={`${s.max_drawdown_pct}%`}
                sub={s.followed_plan_pct === null ? '尚無檢討' : `照計畫執行 ${s.followed_plan_pct}%`} />
            </div>
            {s.equity_curve.length > 1 && <EquityChart data={s.equity_curve} initial={a.initial_cash} />}
            {s.mistakes.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-slate-700 mb-2">哪些錯誤讓你虧最多（來自自我檢討）</h4>
                <table className="w-full text-sm tabular-nums">
                  <thead className="text-xs text-slate-500 border-b">
                    <tr className="text-right"><th className="text-left font-medium py-1.5">錯誤</th><th className="font-medium">次數</th><th className="font-medium">合計損益</th><th className="font-medium">合計 R</th></tr>
                  </thead>
                  <tbody>
                    {s.mistakes.map((m) => (
                      <tr key={m.key} className="text-right border-b border-slate-100 last:border-0">
                        <td className="text-left py-1.5">{m.label}</td><td>{m.count}</td>
                        <td className={upDownClass(m.pnl)}>{ntd(m.pnl, true)}</td><td>{m.r.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>
      <TradeList title="已結束" trades={closed} empty="還沒有結束的交易。" />
      <TradeList title="已取消" trades={by('cancelled')} empty="" hideWhenEmpty />
      <NotifyCard />
      <SourceNote>
        模擬成交規則：只用每日開高低收判斷。市價單以下一個交易日開盤價成交；限價單在最低價碰到時成交；
        同一天同時碰到停損與目標價時，一律當作先停損；跳空時以開盤價成交。價格資料來自 FinMind。
      </SourceNote>
    </>
  );
}

function TradeList({ title, trades, empty, hideWhenEmpty }: { title: string; trades: TradeSummary[]; empty: string; hideWhenEmpty?: boolean }) {
  if (hideWhenEmpty && !trades.length) return null;
  return (
    <Card title={`${title}（${trades.length}）`}>
      {!trades.length ? <p className="text-sm text-slate-500">{empty}</p> : (
        <ul className="divide-y divide-slate-100 -my-2">
          {trades.map((t) => <TradeRow key={t.id} t={t} />)}
        </ul>
      )}
    </Card>
  );
}

function TradeRow({ t }: { t: TradeSummary }) {
  const st = TRADE_STATUS[t.status];
  let detail = '';
  if (t.status === 'planned') {
    detail = `${t.order_type === 'market' ? '開盤市價' : `限價 ${price(t.limit_price)}`}・停損 ${price(t.stop_price)}・目標 ${price(t.target_price)}`;
  } else if (t.status === 'open') {
    detail = `成本 ${price(t.entry_price)}・現價 ${price(t.last_close?.price)}・停損 ${price(t.stop_price)}・目標 ${price(t.target_price)}`;
  } else if (t.status === 'closed') {
    detail = `${t.entry_date} 進 ${price(t.entry_price)} → ${t.exit_date} 出 ${price(t.exit_price)}・${EXIT_REASON[t.exit_reason!]}`;
  } else {
    detail = t.cancel_reason === 'expired' ? '5 個交易日內沒有成交' : t.cancel_reason === 'insufficient_cash' ? '資金不足' : '手動取消';
  }
  const money = t.status === 'closed' ? t.pnl : t.status === 'open' ? t.unrealized : null;
  const r = t.status === 'closed' ? t.r_multiple : t.status === 'open' ? t.unrealized_r : null;
  return (
    <li>
      <Link href={`/trades/${t.id}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 group">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold group-hover:text-indigo-600">{t.stock_name} {t.ticker}</span>
            <Badge cls={st.cls}>{st.label}</Badge>
            {t.status === 'closed' && !t.reviewed && <Badge cls="text-amber-700 bg-amber-50 border-amber-200">待檢討</Badge>}
          </div>
          <p className="text-xs text-slate-500 mt-0.5 tabular-nums">{shares(t.shares)}・{detail}</p>
        </div>
        {money !== null && money !== undefined && (
          <div className={`text-right tabular-nums ${upDownClass(money)}`}>
            <div className="font-semibold">{ntd(money, true)}</div>
            {r !== null && r !== undefined && <div className="text-xs">{r > 0 ? '+' : ''}{r.toFixed(2)}R{t.status === 'open' ? '（未實現）' : ''}</div>}
          </div>
        )}
      </Link>
    </li>
  );
}

function NotifyCard() {
  const [s, setS] = useState<NotifyStatus | null>(null);
  const [msg, setMsg] = useState('');
  useEffect(() => { api<NotifyStatus>('/notify/status').then(setS).catch(() => setS(null)); }, []);
  const test = async () => {
    setMsg('');
    try {
      await api('/notify/test', { method: 'POST' });
      setMsg('測試信已寄出，請檢查信箱。');
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : '寄送失敗');
    }
  };
  if (!s) return null;
  const last = s.runs[0];
  return (
    <Card title="收盤後 Email 通知" subtitle={`每個交易日台灣時間 ${s.check_hour}:00 後自動更新成交、停損、達標與警示，有變化才寄信`}
      action={s.configured && <button onClick={test} className="inline-flex items-center gap-1.5 text-sm border border-slate-300 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50"><Mail className="w-4 h-4" aria-hidden />寄測試信</button>}>
      <div className="text-sm text-slate-600 space-y-1">
        {s.configured ? <p>寄到 {s.to}。</p> : <p className="text-amber-700">還沒設定：需要在後端設定 GMAIL_USER 與 GMAIL_APP_PASSWORD。</p>}
        {last && <p>上次檢查：{last.run_date}（{last.status === 'done' ? `${last.detail?.events ?? 0} 則更新${last.detail?.emailed ? '，已寄信' : ''}` : `失敗：${last.detail?.error ?? ''}`}）・{dateTime(last.created_at)}</p>}
        {msg && <p className="text-indigo-700">{msg}</p>}
      </div>
    </Card>
  );
}
