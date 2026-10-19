export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, init);
  } catch {
    throw new ApiError('無法連線到後端服務，請稍後再試。');
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // FastAPI validation errors (422) carry a list of field errors instead of a message.
    const detail = typeof body?.detail === 'string' ? body.detail
      : res.status === 422 ? '輸入內容格式不正確，請檢查後再送出。' : null;
    throw new ApiError(detail ?? `後端回傳錯誤（${res.status}）`);
  }
  return body as T;
}

export interface Stock {
  stock_id: string;
  name: string;
  industries: string[];
  market: string;
}

export interface MonthRevenue {
  period: string;
  year: number;
  month: number;
  revenue: number;
  yoy: number | null;
  mom: number | null;
}

export interface RevenueSummary {
  period: string;
  revenue: number;
  yoy: number | null;
  mom: number | null;
  ytd_revenue: number;
  ytd_yoy: number | null;
}

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume_lots: number;
}

export interface FlowPoint {
  date: string;
  foreign: number;
  trust: number;
  dealer: number;
  total: number;
}

export interface Overview {
  stock: Stock;
  latest: {
    date: string;
    close: number;
    change: number | null;
    change_pct: number | null;
    volume_lots: number;
    high_52w: number;
    low_52w: number;
  } | null;
  prices: PricePoint[];
  institutional: FlowPoint[];
  institutional_sums: Record<string, number>;
  revenue_summary: RevenueSummary | null;
  monthly_revenue: MonthRevenue[];
}

export type CheckStatus = 'good' | 'warn' | 'bad' | 'na';

export interface Check {
  id: string;
  title: string;
  status: CheckStatus;
  value: string;
  detail: string;
}

export interface Quarter {
  date: string;
  quarter: string;
  revenue: number | null;
  gross_profit: number | null;
  operating_income: number | null;
  non_operating: number | null;
  pretax_income: number | null;
  net_income: number | null;
  eps: number | null;
  operating_cash_flow: number | null;
  capex: number | null;
  receivables: number | null;
  inventories: number | null;
}

export interface Xray {
  stock: Stock;
  score: number | null;
  grade: string;
  checks: Check[];
  revenue_summary: RevenueSummary | null;
  monthly_revenue: MonthRevenue[];
  quarters: Quarter[];
  data_as_of: { month: string | null; quarter: string | null };
}

export interface AiReport {
  status: 'none' | 'pending' | 'done' | 'error';
  report_date?: string;
  error?: string | null;
  /** headline plus one string list per section (keys depend on the reading). */
  content?: ({ headline: string } & Record<string, any>) | null;
}

export type MetricKey = 'revenue_yoy' | 'gross_margin' | 'institutional_net_buy';
export type JobStatus = 'none' | 'pending' | 'done' | 'error';

export interface MetricMeta {
  label: string;
  unit: string;
  description: string;
  source: string;
}

export interface DecisionSummary {
  id: number;
  ticker: string;
  stock_name: string;
  thesis: string;
  conviction: number;
  created_at: string;
  updated_at: string;
  monitor_count: number;
  skeptic: { status: JobStatus; passed: number; failed: number } | null;
}

export interface Monitor {
  id: number;
  metric: MetricKey;
  label: string;
  unit: string;
  description: string;
  data_source: string;
  operator: '>=' | '<=';
  threshold: number;
  rationale: string | null;
  source: 'ai' | 'manual';
}

export interface MonitorStatus extends Monitor {
  current: { value?: number; as_of?: string; note?: string; error?: string };
  holds: boolean | null;
}

export interface SkepticAnswer {
  id: number;
  question_index: number;
  rebuttal: string;
  status: JobStatus;
  verdict: 'Pass' | 'Fail' | null;
  reason: string | null;
  error: string | null;
  created_at: string;
}

export interface SkepticQuestion {
  index: number;
  risk_type: string;
  question: string;
  evidence: string;
  answer: SkepticAnswer | null;
}

export interface SkepticReview {
  id: number;
  status: JobStatus;
  error: string | null;
  data_as_of: { month: string | null; quarter: string | null } | null;
  created_at: string;
  questions: SkepticQuestion[];
}

export interface DecisionStep {
  id: number;
  step_type: string;
  content: any;
  created_at: string;
}

export interface DecisionDetail extends DecisionSummary {
  monitor_status: JobStatus;
  monitor_error: string | null;
  monitors: Monitor[];
  review: SkepticReview | null;
  steps: DecisionStep[];
}

export function jsonBody(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

// --- Swing checklist -----------------------------------------------------------------

export interface SwingPricePoint extends PricePoint {
  ma20: number | null;
  ma60: number | null;
}

export interface ChipPoint {
  date: string;
  margin_balance: number;
  short_balance: number;
  sbl_balance: number | null;
  foreign_ratio: number | null;
  day_trade_ratio: number | null;
}

export interface Defense {
  date: string;
  close: number;
  ma20: number | null;
  ma60: number | null;
  low10: number;
  low20: number;
  low60: number;
  high20: number;
  high60: number;
  suggested_stop: number;
  stop_basis: string;
  stop_distance_pct: number;
  suggested_target: number;
}

export interface Swing {
  stock: Stock;
  checks: Check[];
  defense: Defense | null;
  prices: SwingPricePoint[];
  chips: ChipPoint[];
  institutional: FlowPoint[];
  data_as_of: { price: string | null; chips: string | null };
}

// --- Paper trading ---------------------------------------------------------------------

export type TradeStatus = 'planned' | 'open' | 'closed' | 'cancelled';

export interface AccountSummary {
  initial_cash: number;
  risk_pct: number;
  cash: number;
  reserved: number;
  available: number;
  market_value: number;
  equity: number;
  return_pct: number;
  risk_budget: number;
}

export interface TradeStats {
  closed: number;
  win_rate: number | null;
  avg_r: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  realized_pnl: number;
  max_drawdown_pct: number;
  followed_plan_pct: number | null;
  unreviewed: number;
  equity_curve: { date: string; equity: number; trade_id: number }[];
  mistakes: { key: string; label: string; count: number; pnl: number; r: number }[];
}

export interface TradeSummary {
  id: number;
  ticker: string;
  stock_name: string;
  status: TradeStatus;
  order_type: 'market' | 'limit';
  limit_price: number | null;
  ref_price: number;
  ref_date: string;
  plan_date: string;
  shares: number;
  initial_stop: number;
  stop_price: number;
  target_price: number;
  entry_date: string | null;
  entry_price: number | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: 'stop' | 'target' | 'manual' | null;
  exit_requested_date: string | null;
  cancel_reason: string | null;
  risk_amount: number;
  reward_risk: number | null;
  pnl: number | null;
  r_multiple: number | null;
  reviewed: boolean;
  created_at: string;
  last_close?: { date: string; price: number };
  unrealized?: number;
  unrealized_r?: number | null;
}

export interface AiJob<T> {
  status: JobStatus;
  content: T | null;
  error: string | null;
}

export interface PlanCritique {
  verdict: '計畫合理' | '需要調整' | '不建議執行';
  summary: string;
  strengths: string[];
  risks: string[];
  plan_issues: string[];
}

export interface TradeReviewAi {
  process_grade: 'A' | 'B' | 'C' | 'D';
  summary: string;
  went_well: string[];
  went_wrong: string[];
  lesson: string;
}

export interface TradeDetail extends TradeSummary {
  thesis: string;
  checklist: { checks: Check[]; defense: Defense; data_as_of: Swing['data_as_of'] } | null;
  high_since_entry: number | null;
  low_since_entry: number | null;
  followed_plan: boolean | null;
  mistakes: string[];
  lesson: string | null;
  critique_status: JobStatus;
  critique: PlanCritique | null;
  critique_error: string | null;
  ai_review_status: JobStatus;
  ai_review: TradeReviewAi | null;
  ai_review_error: string | null;
  events: { id: number; event_type: string; bar_date: string | null; content: any; created_at: string }[];
}

export interface PaperOverview {
  account: AccountSummary;
  stats: TradeStats;
  trades: TradeSummary[];
  mistake_options: Record<string, string>;
}

export interface NotifyStatus {
  configured: boolean;
  to: string | null;
  check_hour: number;
  runs: { run_date: string; status: string; detail: any; created_at: string | null }[];
}

// --- Earnings calls -------------------------------------------------------------------------

export interface EarningsCall {
  id: number;
  filename: string;
  size: number;
  status: JobStatus;
  error: string | null;
  created_at: string | null;
  content: {
    period: string;
    headline: string;
    segments: { name: string; share_pct: number | null; trend: string; note: string }[];
    growth_drivers: string[];
    one_off_items: string[];
    guidance: string[];
    risks: string[];
    consistency: string[];
    model: string;
  } | null;
}
