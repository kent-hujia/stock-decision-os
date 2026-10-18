"use client";

import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { FlowPoint, MonthRevenue, PricePoint } from '@/lib/api';
import { lots, pct, yi } from '@/lib/format';

// Categorical slots 1-3 of the validated reference palette (safe for color-blind readers).
const SERIES = { blue: '#2a78d6', orange: '#eb6834', aqua: '#1baf7a' };
// Taiwan market convention: red = up, green = down.
const UP = '#d03b3b';
const DOWN = '#0ca30c';
const GRID = '#e5e7eb';
const AXIS = { fontSize: 12, fill: '#64748b' };

function TooltipBox({ title, rows }: { title: string; rows: [string, string, string?][] }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-md px-3 py-2 text-xs">
      <div className="font-medium text-slate-700 mb-1">{title}</div>
      {rows.map(([label, value, color]) => (
        <div key={label} className="flex items-center gap-2 text-slate-600">
          {color && <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />}
          <span>{label}</span>
          <span className="ml-auto pl-4 font-medium text-slate-900 tabular-nums">{value}</span>
        </div>
      ))}
    </div>
  );
}

export function PriceChart({ data }: { data: PricePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={40}
          tickFormatter={(d: string) => d.slice(5)} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} domain={['auto', 'auto']}
          tickFormatter={(v: number) => v.toLocaleString('zh-TW')} />
        <Tooltip
          cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as PricePoint;
            return <TooltipBox title={p.date} rows={[
              ['收盤', p.close.toLocaleString('zh-TW')],
              ['最高 / 最低', `${p.high.toLocaleString('zh-TW')} / ${p.low.toLocaleString('zh-TW')}`],
              ['成交量', `${p.volume_lots.toLocaleString('zh-TW')} 張`],
            ]} />;
          }}
        />
        <Line type="linear" dataKey="close" stroke={SERIES.blue} strokeWidth={2} dot={false}
          activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const FLOW_SERIES = [
  { key: 'foreign', label: '外資', color: SERIES.blue },
  { key: 'trust', label: '投信', color: SERIES.orange },
  { key: 'dealer', label: '自營商', color: SERIES.aqua },
] as const;

export function InstitutionalChart({ data }: { data: FlowPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} stackOffset="sign" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24}
          tickFormatter={(d: string) => d.slice(5)} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={64}
          tickFormatter={(v: number) => v.toLocaleString('zh-TW')} />
        <ReferenceLine y={0} stroke="#94a3b8" />
        <Tooltip
          cursor={{ fill: 'rgba(148,163,184,0.15)' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as FlowPoint;
            return <TooltipBox title={p.date} rows={[
              ...FLOW_SERIES.map((s) => [s.label, lots(p[s.key]), s.color] as [string, string, string]),
              ['合計', lots(p.total)],
            ]} />;
          }}
        />
        <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12 }}
          formatter={(value: string) => <span className="text-slate-600">{value}</span>} />
        {FLOW_SERIES.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} stackId="flow" fill={s.color}
            stroke="#fff" strokeWidth={1} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function revenueTooltip(p: MonthRevenue) {
  return <TooltipBox title={p.period} rows={[
    ['營收', yi(p.revenue)],
    ['年增', pct(p.yoy)],
    ['月增', pct(p.mom)],
  ]} />;
}

export function RevenueChart({ data }: { data: MonthRevenue[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={16}
          tickFormatter={(p: string) => p.slice(2)} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={64}
          tickFormatter={(v: number) => `${Math.round(v / 1e8).toLocaleString('zh-TW')}億`} />
        <Tooltip cursor={{ fill: 'rgba(148,163,184,0.15)' }}
          content={({ active, payload }) => active && payload?.length ? revenueTooltip(payload[0].payload) : null} />
        <Bar dataKey="revenue" fill={SERIES.blue} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function YoyChart({ data }: { data: MonthRevenue[] }) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={16}
          tickFormatter={(p: string) => p.slice(2)} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={64} tickFormatter={(v: number) => `${v}%`} />
        <ReferenceLine y={0} stroke="#94a3b8" />
        <Tooltip cursor={{ fill: 'rgba(148,163,184,0.15)' }}
          content={({ active, payload }) => active && payload?.length ? revenueTooltip(payload[0].payload) : null} />
        <Bar dataKey="yoy" radius={[2, 2, 2, 2]} maxBarSize={28} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.period} fill={(d.yoy ?? 0) >= 0 ? UP : DOWN} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
