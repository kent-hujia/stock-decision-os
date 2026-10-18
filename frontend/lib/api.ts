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
    throw new ApiError(body?.detail ?? `後端回傳錯誤（${res.status}）`);
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
  content?: {
    headline: string;
    growth_sources: string[];
    risks: string[];
    watch_items: string[];
    score: number | null;
    data_as_of: { month: string | null; quarter: string | null };
  } | null;
}
