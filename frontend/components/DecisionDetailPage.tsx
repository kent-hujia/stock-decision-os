"use client";

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { CheckCircle2, CircleSlash, Loader2, RefreshCw, Sparkles, Trash2, XCircle } from 'lucide-react';
import {
  api, API_URL, ApiError, jsonBody,
  type DecisionDetail, type DecisionStep, type MetricKey, type MetricMeta, type MonitorStatus, type SkepticQuestion,
} from '@/lib/api';
import { dateTime } from '@/lib/format';
import { Badge, Card, ErrorBox, Loading, SourceNote } from '@/components/ui';

const POLL_MS = 4000;
const PRIMARY_BTN = 'inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-60';
const SECONDARY_BTN = 'inline-flex items-center gap-1.5 text-sm border border-slate-300 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 disabled:opacity-60';
const INPUT = 'border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

const errMsg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function isBusy(d: DecisionDetail): boolean {
  return d.monitor_status === 'pending' || d.review?.status === 'pending'
    || !!d.review?.questions.some((q) => q.answer?.status === 'pending');
}

export default function DecisionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => api<DecisionDetail>(`/decisions/${id}`)
    .then(setData)
    .catch((e) => setError(errMsg(e, '載入失敗'))), [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!data || !isBusy(data)) return;
    const timer = setTimeout(load, POLL_MS);
    return () => clearTimeout(timer);
  }, [data, load]);

  /** Run an action that returns the updated decision; errors are returned for the caller to show. */
  const act = useCallback(async (path: string, init: RequestInit): Promise<string> => {
    try {
      setData(await api<DecisionDetail>(`/decisions/${id}${path}`, init));
      return '';
    } catch (e) {
      return errMsg(e, '操作失敗');
    }
  }, [id]);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading text="正在讀取決策…" />;

  return (
    <div className="space-y-6">
      <Header d={data} />
      <ThesisCard d={data} act={act} />
      <MonitorCard d={data} act={act} />
      <SkepticCard d={data} act={act} />
      <HistoryCard steps={data.steps} />
    </div>
  );
}

type Act = (path: string, init: RequestInit) => Promise<string>;

function Header({ d }: { d: DecisionDetail }) {
  const router = useRouter();
  const [error, setError] = useState('');
  const remove = async () => {
    if (!confirm(`確定要刪除 ${d.stock_name} 的這筆決策與所有紀錄嗎？`)) return;
    try {
      await fetchDelete(`/decisions/${d.id}`);
      router.push('/decisions');
    } catch (e) {
      setError(errMsg(e, '刪除失敗'));
    }
  };
  return (
    <header className="space-y-2">
      <Link href="/decisions" className="text-sm text-slate-500 hover:text-indigo-600">← 所有決策</Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">{d.stock_name} {d.ticker}</h2>
          <p className="text-sm text-slate-500">
            建立於 {dateTime(d.created_at)}・
            <Link href={`/?ticker=${d.ticker}`} className="hover:text-indigo-600">個股總覽</Link>・
            <Link href={`/analysis?ticker=${d.ticker}`} className="hover:text-indigo-600">營收 X 光</Link>
          </p>
        </div>
        <button onClick={remove} className={SECONDARY_BTN}>
          <Trash2 className="w-4 h-4" aria-hidden />刪除
        </button>
      </div>
      {error && <ErrorBox message={error} />}
    </header>
  );
}

async function fetchDelete(path: string) {
  // DELETE returns 204 with no body, which api() can't parse as JSON on success.
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, { method: 'DELETE' });
  } catch {
    throw new ApiError('無法連線到後端服務，請稍後再試。');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? `後端回傳錯誤（${res.status}）`);
  }
}

// --- Thesis ----------------------------------------------------------------------

function ThesisCard({ d, act }: { d: DecisionDetail; act: Act }) {
  const [editing, setEditing] = useState(false);
  const [thesis, setThesis] = useState(d.thesis);
  const [conviction, setConviction] = useState(d.conviction);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const open = () => {
    setThesis(d.thesis);
    setConviction(d.conviction);
    setNote('');
    setError('');
    setEditing(true);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const err = await act('', jsonBody('PATCH', { thesis, conviction, note }));
    setBusy(false);
    setError(err);
    if (!err) setEditing(false);
  };

  return (
    <Card title="投資論點" subtitle="修改論點或信心時會留下紀錄，方便日後回顧當初怎麼想"
      action={!editing && <button onClick={open} className={SECONDARY_BTN}>修改論點／信心</button>}>
      {!editing ? (
        <div className="space-y-3">
          <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">{d.thesis}</p>
          <ConvictionBar value={d.conviction} />
        </div>
      ) : (
        <form onSubmit={save} className="space-y-3">
          <textarea value={thesis} onChange={(e) => setThesis(e.target.value)} rows={4} minLength={10} maxLength={3000} required
            className={`${INPUT} w-full leading-relaxed`} aria-label="投資論點" />
          <label className="block">
            <span className="text-sm font-medium text-slate-700">信心程度：<span className="tabular-nums text-indigo-600">{conviction}</span>/10</span>
            <input type="range" min={1} max={10} value={conviction} onChange={(e) => setConviction(Number(e.target.value))}
              className="mt-2 w-full accent-indigo-600" />
          </label>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="為什麼改變想法？（選填）"
            className={`${INPUT} w-full`} aria-label="修改原因" />
          {error && <ErrorBox message={error} />}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className={PRIMARY_BTN}>儲存</button>
            <button type="button" onClick={() => setEditing(false)} className={SECONDARY_BTN}>取消</button>
          </div>
        </form>
      )}
    </Card>
  );
}

function ConvictionBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-slate-500">信心</span>
      <div className="flex gap-1" aria-label={`信心 ${value}/10`}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`w-4 h-2 rounded-sm ${i < value ? 'bg-indigo-500' : 'bg-slate-200'}`} />
        ))}
      </div>
      <span className="font-semibold tabular-nums">{value}/10</span>
    </div>
  );
}

// --- Thesis monitoring -------------------------------------------------------------

function formatValue(v: number | undefined, unit: string): string {
  if (v === undefined) return '—';
  if (unit === '張') return `${v > 0 ? '+' : ''}${v.toLocaleString('zh-TW')} 張`;
  return `${v.toFixed(1)}%`;
}

function MonitorCard({ d, act }: { d: DecisionDetail; act: Act }) {
  const [statuses, setStatuses] = useState<MonitorStatus[] | null>(null);
  const [statusError, setStatusError] = useState('');
  const [actionError, setActionError] = useState('');
  const monitorKey = d.monitors.map((m) => m.id).join(',');

  useEffect(() => {
    if (!monitorKey) {
      setStatuses([]);
      return;
    }
    setStatuses(null);
    setStatusError('');
    api<MonitorStatus[]>(`/decisions/${d.id}/monitors/status`)
      .then(setStatuses)
      .catch((e) => setStatusError(errMsg(e, '讀取目前數值失敗')));
  }, [d.id, monitorKey]);

  const extract = async () => setActionError(await act('/monitors/extract', { method: 'POST' }));
  const remove = async (mid: number) => setActionError(await act(`/monitors/${mid}`, { method: 'DELETE' }));

  return (
    <Card title="論點監控" subtitle="論點成立時應該維持的條件；目前數值每次開啟頁面時從 FinMind 重新計算"
      action={d.monitor_status !== 'pending' && (
        <button onClick={extract} className={SECONDARY_BTN}>
          <Sparkles className="w-4 h-4" aria-hidden />{d.monitor_status === 'done' ? '重新從論點萃取' : '用 AI 從論點萃取'}
        </button>
      )}>
      <div className="space-y-4">
        {d.monitor_status === 'pending' && (
          <p className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
            Claude 正在從論點找出可以追蹤的條件，完成後會自動顯示…
          </p>
        )}
        {d.monitor_status === 'error' && <ErrorBox message={`AI 萃取監控條件失敗：${d.monitor_error ?? '未知錯誤'} 可以重試，或在下方手動新增。`} />}
        {d.monitor_status === 'done' && !d.monitors.some((m) => m.source === 'ai') && (
          <p className="text-sm text-slate-500">AI 在論點中沒有找到可以用月營收、毛利率或法人買賣超檢驗的具體條件。</p>
        )}
        {actionError && <ErrorBox message={actionError} />}
        {statusError && <ErrorBox message={statusError} />}
        {d.monitors.length > 0 && (
          <div className="grid md:grid-cols-2 gap-3">
            {d.monitors.map((m) => {
              const s = statuses?.find((x) => x.id === m.id);
              return <MonitorItem key={m.id} m={s ?? { ...m, current: {}, holds: null }} loading={!s && !statusError} onRemove={() => remove(m.id)} />;
            })}
          </div>
        )}
        <AddMonitorForm act={act} />
      </div>
    </Card>
  );
}

function MonitorItem({ m, loading, onRemove }: { m: MonitorStatus; loading: boolean; onRemove: () => void }) {
  const state = m.holds === true
    ? { label: '論點成立', icon: CheckCircle2, cls: 'text-green-700 bg-green-50 border-green-200' }
    : m.holds === false
      ? { label: '觸發警示', icon: XCircle, cls: 'text-red-700 bg-red-50 border-red-200' }
      : { label: loading ? '計算中' : '無資料', icon: CircleSlash, cls: 'text-slate-500 bg-slate-50 border-slate-200' };
  const Icon = state.icon;
  return (
    <article className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-semibold">{m.label}</h4>
        <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${state.cls}`}>
          <Icon className="w-3.5 h-3.5" aria-hidden />{state.label}
        </span>
      </div>
      <div className="flex items-baseline gap-3 mt-1 tabular-nums">
        <span className="text-lg font-semibold">{loading ? '…' : formatValue(m.current.value, m.unit)}</span>
        <span className="text-sm text-slate-500">條件 {m.operator === '>=' ? '≥' : '≤'} {formatValue(m.threshold, m.unit)}</span>
      </div>
      {m.current.note && <p className="text-xs text-slate-500 mt-0.5">資料期間：{m.current.note}</p>}
      {m.current.error && <p className="text-xs text-red-700 mt-0.5">{m.current.error}</p>}
      {m.rationale && <p className="text-sm text-slate-600 mt-2 leading-relaxed">{m.rationale}</p>}
      <div className="flex items-center justify-between gap-2 mt-2">
        <SourceNote>{m.source === 'ai' ? 'AI 從論點萃取' : '手動新增'}・{m.data_source}</SourceNote>
        <button onClick={onRemove} className="text-xs text-slate-400 hover:text-red-600 shrink-0">移除</button>
      </div>
    </article>
  );
}

function AddMonitorForm({ act }: { act: Act }) {
  const [metrics, setMetrics] = useState<Record<MetricKey, MetricMeta> | null>(null);
  const [open, setOpen] = useState(false);
  const [metric, setMetric] = useState<MetricKey>('revenue_yoy');
  const [operator, setOperator] = useState<'>=' | '<='>('>=');
  const [threshold, setThreshold] = useState('');
  const [rationale, setRationale] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && !metrics) {
      api<Record<MetricKey, MetricMeta>>('/decisions/meta/metrics').then(setMetrics).catch((e) => setError(errMsg(e, '載入指標失敗')));
    }
  }, [open, metrics]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const err = await act('/monitors', jsonBody('POST', { metric, operator, threshold: Number(threshold), rationale }));
    setError(err);
    if (!err) {
      setThreshold('');
      setRationale('');
      setOpen(false);
    }
  };

  if (!open) {
    return <button onClick={() => setOpen(true)} className="text-sm text-indigo-600 hover:text-indigo-800">+ 手動新增監控條件</button>;
  }
  const unit = metrics?.[metric]?.unit ?? '';
  return (
    <form onSubmit={submit} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50">
      <div className="flex flex-wrap items-end gap-2">
        <select value={metric} onChange={(e) => setMetric(e.target.value as MetricKey)} className={INPUT} aria-label="指標">
          {metrics && Object.entries(metrics).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
        </select>
        <select value={operator} onChange={(e) => setOperator(e.target.value as '>=' | '<=')} className={INPUT} aria-label="條件">
          <option value=">=">≥</option>
          <option value="<=">≤</option>
        </select>
        <input type="number" step="any" required value={threshold} onChange={(e) => setThreshold(e.target.value)}
          className={`${INPUT} w-32`} aria-label="門檻" placeholder="門檻" />
        <span className="text-sm text-slate-500 pb-2">{unit}</span>
      </div>
      {metrics && <p className="text-xs text-slate-500">{metrics[metric].description}</p>}
      <input value={rationale} onChange={(e) => setRationale(e.target.value)} maxLength={500}
        placeholder="這個條件對應論點中的哪一點？（選填）" className={`${INPUT} w-full`} aria-label="說明" />
      {error && <ErrorBox message={error} />}
      <div className="flex gap-2">
        <button type="submit" className={PRIMARY_BTN}>新增</button>
        <button type="button" onClick={() => setOpen(false)} className={SECONDARY_BTN}>取消</button>
      </div>
    </form>
  );
}

// --- AI skeptic -----------------------------------------------------------------------

function SkepticCard({ d, act }: { d: DecisionDetail; act: Act }) {
  const r = d.review;
  const [error, setError] = useState('');
  const start = async (regenerate: boolean) => setError(await act(`/skeptic${regenerate ? '?regenerate=true' : ''}`, { method: 'POST' }));

  return (
    <Card title="AI 質疑" subtitle="Claude 扮演放空研究員，只根據這檔股票的財報、月營收、股價與法人數據提出 3 個質疑；逐題反駁後會被評為通過或未通過"
      action={(
        (!r && <button onClick={() => start(false)} className={PRIMARY_BTN}><Sparkles className="w-4 h-4" aria-hidden />開始質疑</button>)
        || (r?.status === 'error' && <button onClick={() => start(true)} className={PRIMARY_BTN}><RefreshCw className="w-4 h-4" aria-hidden />重新產生</button>)
        || (r?.status === 'done' && <button onClick={() => start(true)} className={SECONDARY_BTN}><RefreshCw className="w-4 h-4" aria-hidden />換一組問題</button>)
      )}>
      <div className="space-y-4">
        {error && <ErrorBox message={error} />}
        {!r && <p className="text-sm text-slate-500">還沒有質疑。按右上角按鈕，大約需要 1 分鐘。</p>}
        {r?.status === 'pending' && (
          <p className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
            Claude 正在閱讀財報數字並找出論點的弱點，大約需要 1 分鐘，完成後會自動顯示…
          </p>
        )}
        {r?.status === 'error' && <ErrorBox message={`產生質疑失敗：${r.error ?? '未知錯誤'}`} />}
        {r?.status === 'done' && (
          <>
            {r.questions.map((q) => <QuestionItem key={`${r.id}-${q.index}`} q={q} act={act} />)}
            <SourceNote>
              產生於 {dateTime(r.created_at)}・依據資料：月營收至 {r.data_as_of?.month ?? '—'}、季報至 {r.data_as_of?.quarter ?? '—'}・不構成投資建議
            </SourceNote>
          </>
        )}
      </div>
    </Card>
  );
}

function QuestionItem({ q, act }: { q: SkepticQuestion; act: Act }) {
  const a = q.answer;
  const [text, setText] = useState('');
  const [editing, setEditing] = useState(!a);
  const [error, setError] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const err = await act('/skeptic/answers', jsonBody('POST', { question_index: q.index, rebuttal: text }));
    setError(err);
    if (!err) setEditing(false);
  };

  const verdict = a?.verdict === 'Pass'
    ? { label: '通過', icon: CheckCircle2, cls: 'text-green-700 bg-green-50 border-green-200' }
    : { label: '未通過', icon: XCircle, cls: 'text-red-700 bg-red-50 border-red-200' };
  const VerdictIcon = verdict.icon;

  return (
    <article className="border border-slate-200 rounded-xl p-4 space-y-3">
      <div>
        <Badge cls="text-indigo-700 bg-indigo-50 border-indigo-200">{q.risk_type}</Badge>
        <p className="font-medium text-slate-900 mt-2 leading-relaxed">{q.question}</p>
        <p className="text-sm text-slate-500 mt-1 leading-relaxed">依據：{q.evidence}</p>
      </div>

      {a && !editing && (
        <div className="bg-slate-50 rounded-lg p-3 space-y-2">
          <p className="text-sm text-slate-700 whitespace-pre-wrap"><span className="font-medium">你的反駁：</span>{a.rebuttal}</p>
          {a.status === 'pending' && (
            <p className="flex items-center gap-2 text-sm text-slate-600">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden />Claude 正在評分…
            </p>
          )}
          {a.status === 'error' && <ErrorBox message={`評分失敗：${a.error ?? '未知錯誤'}`} />}
          {a.status === 'done' && (
            <div className="space-y-1">
              <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${verdict.cls}`}>
                <VerdictIcon className="w-3.5 h-3.5" aria-hidden />{verdict.label}
              </span>
              <p className="text-sm text-slate-700 leading-relaxed">{a.reason}</p>
            </div>
          )}
          {a.status !== 'pending' && (
            <button onClick={() => { setText(a.rebuttal); setEditing(true); }} className="text-sm text-indigo-600 hover:text-indigo-800">
              {a.status === 'error' ? '重新送出' : '修改反駁再評一次'}
            </button>
          )}
        </div>
      )}

      {editing && (
        <form onSubmit={submit} className="space-y-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} required maxLength={2000} rows={3}
            placeholder="用數據或可驗證的理由回應這個質疑…" className={`${INPUT} w-full leading-relaxed`} aria-label="反駁" />
          {error && <ErrorBox message={error} />}
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY_BTN}>送出反駁</button>
            {a && <button type="button" onClick={() => setEditing(false)} className={SECONDARY_BTN}>取消</button>}
          </div>
        </form>
      )}
    </article>
  );
}

// --- History ---------------------------------------------------------------------------

function cond(c: { label: string; operator: string; threshold: number; unit: string }) {
  return `${c.label} ${c.operator === '>=' ? '≥' : '≤'} ${formatValue(c.threshold, c.unit)}`;
}

function describeStep(s: DecisionStep): { title: string; body?: string } {
  const c = s.content ?? {};
  switch (s.step_type) {
    case 'created':
      return { title: `建立決策，信心 ${c.conviction}/10`, body: c.thesis };
    case 'conviction_updated':
      return { title: `信心 ${c.from} → ${c.to}`, body: c.note ?? undefined };
    case 'thesis_updated':
      return { title: '修改投資論點', body: [c.to, c.note && `原因：${c.note}`].filter(Boolean).join('\n') };
    case 'monitors_extracted':
      return {
        title: `AI 萃取出 ${c.monitors?.length ?? 0} 個監控條件`,
        body: (c.monitors ?? []).map(cond).join('\n') || '論點中沒有可量化的條件。',
      };
    case 'monitor_added':
      return { title: `手動新增監控：${cond(c)}` };
    case 'monitor_removed':
      return { title: `移除監控：${cond(c)}` };
    case 'skeptic_questions':
      return { title: 'AI 提出 3 個質疑', body: (c.questions ?? []).map((q: any) => `【${q.risk_type}】${q.question}`).join('\n') };
    case 'rebuttal_graded':
      return {
        title: `反駁【${c.risk_type}】：${c.verdict === 'Pass' ? '通過' : '未通過'}`,
        body: `問：${c.question}\n答：${c.rebuttal}\n評：${c.reason}`,
      };
    default:
      return { title: s.step_type };
  }
}

function HistoryCard({ steps }: { steps: DecisionStep[] }) {
  return (
    <Card title="決策紀錄" subtitle="這筆決策的每一步，最新的在最上面">
      <ol className="relative border-l border-slate-200 ml-2 space-y-5">
        {steps.map((s) => {
          const { title, body } = describeStep(s);
          return (
            <li key={s.id} className="ml-4">
              <span className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-indigo-200 border-2 border-white" aria-hidden />
              <div className="text-xs text-slate-500 tabular-nums">{dateTime(s.created_at)}</div>
              <div className="text-sm font-medium text-slate-900">{title}</div>
              {body && <p className="text-sm text-slate-600 mt-1 whitespace-pre-wrap leading-relaxed">{body}</p>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
