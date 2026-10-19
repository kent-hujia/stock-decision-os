"use client";

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, RefreshCw, Sparkles } from 'lucide-react';
import {
  api, ApiError, jsonBody, type PaperOverview, type Swing, type TradeDetail,
} from '@/lib/api';
import { dateTime, ntd, price, shares, upDownClass } from '@/lib/format';
import { SwingPriceChart } from '@/components/Charts';
import CheckCard, { SWING_LABELS } from '@/components/CheckCard';
import { EXIT_REASON, TRADE_STATUS } from '@/components/TradesPage';
import { Badge, Card, ErrorBox, Loading, SourceNote, Stat } from '@/components/ui';

const POLL_MS = 4000;
const PRIMARY_BTN = 'inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-60';
const SECONDARY_BTN = 'inline-flex items-center gap-1.5 text-sm border border-slate-300 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 disabled:opacity-60';
const INPUT = 'border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';
const errMsg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

type Act = (path: string, init: RequestInit) => Promise<string>;

export default function TradeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<TradeDetail | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => api<TradeDetail>(`/paper/trades/${id}`)
    .then(setT).catch((e) => setError(errMsg(e, '載入失敗'))), [id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!t || (t.critique_status !== 'pending' && t.ai_review_status !== 'pending')) return;
    const timer = setTimeout(load, POLL_MS);
    return () => clearTimeout(timer);
  }, [t, load]);

  const act = useCallback<Act>(async (path, init) => {
    try {
      setT(await api<TradeDetail>(`/paper/trades/${id}${path}`, init));
      return '';
    } catch (e) {
      return errMsg(e, '操作失敗');
    }
  }, [id]);

  if (error) return <ErrorBox message={error} />;
  if (!t) return <Loading text="正在更新模擬成交…" />;
  const st = TRADE_STATUS[t.status];

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link href="/trades" className="text-sm text-slate-500 hover:text-indigo-600">← 模擬交易</Link>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-bold">{t.stock_name} {t.ticker}</h2>
          <Badge cls={st.cls}>{st.label}</Badge>
        </div>
        <p className="text-sm text-slate-500">
          {t.plan_date} 建立計畫・{shares(t.shares)}・
          <Link href={`/swing?ticker=${t.ticker}`} className="hover:text-indigo-600">目前的波段檢查</Link>
        </p>
      </header>
      <PositionCard t={t} act={act} />
      <PriceCard t={t} />
      <Card title="進場理由">
        <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">{t.thesis}</p>
      </Card>
      <CritiqueCard t={t} act={act} />
      {t.status === 'closed' && <ReviewCard t={t} act={act} />}
      {t.status === 'closed' && <AiReviewCard t={t} act={act} />}
      {t.checklist && (
        <Card title="下單當時的波段檢查" subtitle={`資料截至 ${t.checklist.data_as_of?.price ?? t.ref_date}，之後不會再變動，方便事後對照`}>
          <div className="grid md:grid-cols-2 gap-3">
            {t.checklist.checks.map((c) => <CheckCard key={c.id} check={c} labels={SWING_LABELS} />)}
          </div>
        </Card>
      )}
      <EventsCard t={t} />
    </div>
  );
}

function PositionCard({ t, act }: { t: TradeDetail; act: Act }) {
  const router = useRouter();
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [stop, setStop] = useState(String(t.stop_price));
  const [target, setTarget] = useState(String(t.target_price));
  const [note, setNote] = useState('');

  const run = async (path: string, init: RequestInit, confirmText?: string) => {
    if (confirmText && !confirm(confirmText)) return;
    setError(await act(path, init));
  };
  const save = async (e: FormEvent) => {
    e.preventDefault();
    const err = await act('', jsonBody('PATCH', { stop_price: Number(stop), target_price: Number(target), note }));
    setError(err);
    if (!err) setEditing(false);
  };

  const remove = async () => {
    if (!confirm('刪除這筆沒有成交的委託與它的紀錄？')) return;
    try {
      await api(`/paper/trades/${t.id}`, { method: 'DELETE' });
      router.push('/trades');
    } catch (e) {
      setError(errMsg(e, '刪除失敗'));
    }
  };
  const active = t.status === 'planned' || t.status === 'open';
  return (
    <Card title="部位" action={t.status === 'cancelled' ? (
      <button onClick={remove} className={SECONDARY_BTN}>刪除</button>
    ) : active && !editing && (
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setStop(String(t.stop_price)); setTarget(String(t.target_price)); setNote(''); setEditing(true); }} className={SECONDARY_BTN}>調整停損／目標</button>
        {t.status === 'planned' && <button onClick={() => run('/cancel', { method: 'POST' }, '確定取消這筆委託？')} className={SECONDARY_BTN}>取消委託</button>}
        {t.status === 'planned' && <button onClick={remove} className={SECONDARY_BTN}>刪除</button>}
        {t.status === 'open' && !t.exit_requested_date && (
          <button onClick={() => run('/exit', { method: 'POST' }, '下一個交易日開盤以市價賣出，確定？')} className={SECONDARY_BTN}>開盤市價出場</button>
        )}
      </div>
    )}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {t.status === 'planned' && <>
          <Stat label="委託" value={t.order_type === 'market' ? '開盤市價' : `限價 ${price(t.limit_price)}`} sub={`參考收盤 ${price(t.ref_price)}（${t.ref_date}）`} />
          <Stat label="最多虧損" value={ntd(t.risk_amount)} valueClass="text-green-700" sub={`報酬風險比 ${t.reward_risk ?? '—'} 倍`} />
        </>}
        {t.status !== 'planned' && t.entry_price !== null && (
          <Stat label="進場" value={price(t.entry_price)} sub={t.entry_date ?? ''} />
        )}
        {t.status === 'open' && <>
          <Stat label="現價" value={price(t.last_close?.price)} sub={t.last_close?.date} />
          <Stat label="未實現損益" value={ntd(t.unrealized, true)} valueClass={upDownClass(t.unrealized)}
            sub={t.unrealized_r === null || t.unrealized_r === undefined ? '' : `${t.unrealized_r > 0 ? '+' : ''}${t.unrealized_r}R`} />
        </>}
        {t.status === 'closed' && <>
          <Stat label="出場" value={price(t.exit_price)} sub={`${t.exit_date}・${EXIT_REASON[t.exit_reason!]}`} />
          <Stat label="損益（含成本）" value={ntd(t.pnl, true)} valueClass={upDownClass(t.pnl)}
            sub={t.r_multiple === null ? '' : `${t.r_multiple > 0 ? '+' : ''}${t.r_multiple}R`} />
        </>}
        {t.status !== 'cancelled' && <>
          <Stat label="停損" value={price(t.stop_price)} valueClass="text-green-700"
            sub={t.stop_price !== t.initial_stop ? `原始 ${price(t.initial_stop)}` : '原始設定'} />
          <Stat label="目標" value={price(t.target_price)} valueClass="text-red-600" />
        </>}
        {t.status === 'closed' && t.high_since_entry !== null && (
          <Stat label="持有期間高／低" value={`${price(t.high_since_entry)} / ${price(t.low_since_entry)}`} />
        )}
      </div>
      {t.exit_requested_date && t.status === 'open' && <p className="text-sm text-amber-700 mt-3">已送出出場：下一個交易日開盤以市價賣出。</p>}
      {t.status === 'cancelled' && <p className="text-sm text-slate-600 mt-3">
        委託已取消：{t.cancel_reason === 'expired' ? '5 個交易日內價格沒有碰到委託價' : t.cancel_reason === 'insufficient_cash' ? '成交當天資金不足' : '手動取消'}。
      </p>}
      {editing && (
        <form onSubmit={save} className="mt-4 border border-slate-200 bg-slate-50 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">停損 <input type="number" step="any" value={stop} onChange={(e) => setStop(e.target.value)} className={`${INPUT} w-32 ml-1`} /></label>
            <label className="text-sm">目標 <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} className={`${INPUT} w-32 ml-1`} /></label>
          </div>
          {t.status === 'open' && Number(stop) < t.stop_price && (
            <p className="text-sm text-red-700">你正在把停損往下移，這通常是不願認賠。檢討時會被記錄。</p>
          )}
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="為什麼調整？（選填）" className={`${INPUT} w-full`} />
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY_BTN}>儲存</button>
            <button type="button" onClick={() => setEditing(false)} className={SECONDARY_BTN}>取消</button>
          </div>
        </form>
      )}
      {error && <div className="mt-3"><ErrorBox message={error} /></div>}
    </Card>
  );
}

function PriceCard({ t }: { t: TradeDetail }) {
  const [swing, setSwing] = useState<Swing | null>(null);
  useEffect(() => { api<Swing>(`/stocks/${t.ticker}/swing`).then(setSwing).catch(() => setSwing(null)); }, [t.ticker]);
  if (!swing) return null;
  const from = t.plan_date;
  const start = Math.max(0, swing.prices.findIndex((p) => p.date >= from) - 30);
  return (
    <Card title="走勢" subtitle="計畫前 30 個交易日起；虛線為目前的停損、目標與成交價">
      <SwingPriceChart data={swing.prices.slice(start)} stop={t.status === 'cancelled' ? null : t.stop_price}
        target={t.status === 'cancelled' ? null : t.target_price} entry={t.entry_price} />
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

function JobStatus({ status, error, pendingText }: { status: string; error: string | null; pendingText: string }) {
  if (status === 'pending') {
    return <p className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="w-4 h-4 animate-spin" aria-hidden />{pendingText}</p>;
  }
  if (status === 'error') return <ErrorBox message={`產生失敗：${error ?? '未知錯誤'}`} />;
  return null;
}

function CritiqueCard({ t, act }: { t: TradeDetail; act: Act }) {
  const [error, setError] = useState('');
  const c = t.critique;
  const start = async () => setError(await act('/critique', { method: 'POST' }));
  const verdictCls = c?.verdict === '計畫合理' ? 'text-green-700 bg-green-50 border-green-200'
    : c?.verdict === '需要調整' ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-red-700 bg-red-50 border-red-200';
  return (
    <Card title="AI 計畫質疑" subtitle="Claude 對照下單當時的波段檢查，評估計畫本身是否合理（不預測股價）"
      action={t.critique_status !== 'pending' && (
        <button onClick={start} className={t.critique_status === 'done' ? SECONDARY_BTN : PRIMARY_BTN}>
          {t.critique_status === 'done' ? <RefreshCw className="w-4 h-4" aria-hidden /> : <Sparkles className="w-4 h-4" aria-hidden />}
          {t.critique_status === 'done' ? '重新質疑' : '請 AI 挑戰這份計畫'}
        </button>
      )}>
      <div className="space-y-3">
        {error && <ErrorBox message={error} />}
        {t.critique_status === 'none' && <p className="text-sm text-slate-500">建議在委託成交前先讓 AI 看一次，有問題可以先調整停損或取消委託。</p>}
        <JobStatus status={t.critique_status} error={t.critique_error} pendingText="Claude 正在檢查這份計畫，大約需要 1 分鐘…" />
        {t.critique_status === 'done' && c && <>
          <div className="flex items-center gap-2"><Badge cls={verdictCls}>{c.verdict}</Badge></div>
          <p className="font-medium text-slate-900">{c.summary}</p>
          <List title="做對的地方" items={c.strengths} />
          <List title="被忽略的警訊" items={c.risks} />
          <List title="計畫要調整的地方" items={c.plan_issues} />
        </>}
      </div>
    </Card>
  );
}

function ReviewCard({ t, act }: { t: TradeDetail; act: Act }) {
  const [options, setOptions] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(!t.reviewed);
  const [followed, setFollowed] = useState<boolean>(t.followed_plan ?? true);
  const [mistakes, setMistakes] = useState<string[]>(t.mistakes);
  const [lesson, setLesson] = useState(t.lesson ?? '');
  const [error, setError] = useState('');
  useEffect(() => { api<PaperOverview>('/paper/account').then((o) => setOptions(o.mistake_options)).catch(() => {}); }, []);

  const toggle = (k: string) => setMistakes((m) => (m.includes(k) ? m.filter((x) => x !== k) : [...m, k]));
  const save = async (e: FormEvent) => {
    e.preventDefault();
    const err = await act('/review', jsonBody('POST', { followed_plan: followed, mistakes, lesson }));
    setError(err);
    if (!err) setEditing(false);
  };

  return (
    <Card title="自我檢討" subtitle="先自己檢討，再看 AI 的看法；統計頁會依這裡的錯誤標籤計算虧損來源"
      action={!editing && <button onClick={() => setEditing(true)} className={SECONDARY_BTN}>修改</button>}>
      {!editing ? (
        <div className="space-y-2 text-sm text-slate-700">
          <p>{t.followed_plan ? '✅ 有照計畫執行' : '❌ 沒有照計畫執行'}</p>
          {t.mistakes.length > 0 && <div className="flex flex-wrap gap-2">{t.mistakes.map((m) => <Badge key={m} cls="text-red-700 bg-red-50 border-red-200">{options[m] ?? m}</Badge>)}</div>}
          <p className="whitespace-pre-wrap"><span className="font-medium">學到的事：</span>{t.lesson}</p>
        </div>
      ) : (
        <form onSubmit={save} className="space-y-4">
          <fieldset className="flex gap-4 text-sm">
            <legend className="font-medium text-slate-700 mb-1">有照計畫執行嗎？</legend>
            <label className="flex items-center gap-1.5"><input type="radio" checked={followed} onChange={() => setFollowed(true)} />有</label>
            <label className="flex items-center gap-1.5"><input type="radio" checked={!followed} onChange={() => setFollowed(false)} />沒有</label>
          </fieldset>
          <fieldset>
            <legend className="text-sm font-medium text-slate-700 mb-2">犯了哪些錯？（可複選，沒有就不選）</legend>
            <div className="flex flex-wrap gap-2">
              {Object.entries(options).map(([k, label]) => (
                <button type="button" key={k} onClick={() => toggle(k)} aria-pressed={mistakes.includes(k)}
                  className={`text-sm px-3 py-1 rounded-full border ${mistakes.includes(k) ? 'bg-red-50 border-red-300 text-red-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">這筆交易學到什麼？下次要怎麼做？</span>
            <textarea value={lesson} onChange={(e) => setLesson(e.target.value)} required maxLength={2000} rows={3}
              className={`${INPUT} w-full mt-1 leading-relaxed`} />
          </label>
          {error && <ErrorBox message={error} />}
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY_BTN}>儲存檢討</button>
            {t.reviewed && <button type="button" onClick={() => setEditing(false)} className={SECONDARY_BTN}>取消</button>}
          </div>
        </form>
      )}
    </Card>
  );
}

function AiReviewCard({ t, act }: { t: TradeDetail; act: Act }) {
  const [error, setError] = useState('');
  const r = t.ai_review;
  const start = async () => setError(await act('/ai-review', { method: 'POST' }));
  return (
    <Card title="AI 交易檢討" subtitle="Claude（Sonnet）看進場時的檢查、持有期間與出場後 10 天的走勢，評的是過程而不是輸贏"
      action={t.ai_review_status !== 'pending' && (
        <button onClick={start} className={t.ai_review_status === 'done' ? SECONDARY_BTN : PRIMARY_BTN}>
          <Sparkles className="w-4 h-4" aria-hidden />{t.ai_review_status === 'done' ? '重新檢討' : '請 AI 檢討'}
        </button>
      )}>
      <div className="space-y-3">
        {error && <ErrorBox message={error} />}
        {t.ai_review_status === 'none' && <p className="text-sm text-slate-500">{t.reviewed ? '已有自我檢討，AI 會對照你的說法。' : '建議先寫自我檢討，AI 會對照你的說法。'}出場後過幾天再請 AI 檢討，它能看到出場後的走勢。</p>}
        <JobStatus status={t.ai_review_status} error={t.ai_review_error} pendingText="Claude 正在檢討這筆交易，大約需要 1 分鐘…" />
        {t.ai_review_status === 'done' && r && <>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-bold text-indigo-600">{r.process_grade}</span>
            <p className="font-medium text-slate-900">{r.summary}</p>
          </div>
          <List title="做得好" items={r.went_well} />
          <List title="做得不好" items={r.went_wrong} />
          <p className="text-sm bg-indigo-50 border border-indigo-200 text-indigo-900 rounded-lg px-3 py-2"><span className="font-semibold">下次的規則：</span>{r.lesson}</p>
        </>}
      </div>
    </Card>
  );
}

const EVENT_LABEL: Record<string, (c: any) => string> = {
  planned: (c) => `建立計畫：${c.order_type === 'market' ? '開盤市價' : `限價 ${price(c.limit_price)}`}，停損 ${price(c.stop)}，目標 ${price(c.target)}，${shares(c.shares)}`,
  filled: (c) => `成交：${shares(c.shares)} @ ${price(c.price)}，手續費 ${ntd(c.fee)}`,
  cancelled: (c) => `取消：${c.reason}`,
  stop_moved: (c) => `停損 ${price(c.from)} → ${price(c.to)}${c.note ? `（${c.note}）` : ''}`,
  target_moved: (c) => `目標 ${price(c.from)} → ${price(c.to)}${c.note ? `（${c.note}）` : ''}`,
  exit_requested: () => '送出出場：下一個交易日開盤市價賣出',
  closed: (c) => `${EXIT_REASON[c.reason as keyof typeof EXIT_REASON]} @ ${price(c.price)}${c.gap ? '（跳空，以開盤價成交）' : ''}，損益 ${ntd(c.pnl, true)}${c.r === null ? '' : `（${c.r > 0 ? '+' : ''}${c.r.toFixed(2)}R）`}`,
  alert: (c) => `⚠️ ${c.message}`,
  reviewed: (c) => `自我檢討：${c.followed_plan ? '有' : '沒有'}照計畫${c.mistakes?.length ? `；${c.mistakes.join('、')}` : ''}`,
  plan_critiqued: (c) => `AI 計畫質疑：${c.verdict}`,
  ai_reviewed: (c) => `AI 檢討：過程評分 ${c.process_grade}`,
};

function EventsCard({ t }: { t: TradeDetail }) {
  return (
    <Card title="紀錄" subtitle="最新的在最上面；括號內是對應的交易日">
      <ol className="space-y-2 text-sm">
        {t.events.map((e) => (
          <li key={e.id} className="flex flex-wrap gap-x-3">
            <span className="text-xs text-slate-500 tabular-nums w-36 shrink-0 pt-0.5">{dateTime(e.created_at)}{e.bar_date ? `（${e.bar_date.slice(5)}）` : ''}</span>
            <span className="text-slate-700">{(EVENT_LABEL[e.event_type] ?? (() => e.event_type))(e.content)}</span>
          </li>
        ))}
      </ol>
      <div className="mt-3"><SourceNote>成交、停損與達標是在你打開頁面或每日收盤後檢查時，依當天的真實日 K 判斷。</SourceNote></div>
    </Card>
  );
}
