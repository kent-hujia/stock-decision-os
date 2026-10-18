"use client";

import { useState } from 'react';
import { Search, TrendingUp, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

export default function Home() {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [sentimentData, setSentimentData] = useState<any>(null);

  const handleAnalyze = async () => {
    if (!ticker) return;
    setLoading(true);
    try {
      // Note: Replace with actual Railway URL in production
      const res = await fetch(`http://localhost:8000/api/v1/sentiment/${ticker}`);
      const data = await res.json();
      setSentimentData(data);
    } catch (e) {
      console.error("Failed to fetch sentiment:", e);
      alert("無法連接至後端服務，請確認 API 已啟動");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <header className="flex justify-between items-end">
        <div className="space-y-2">
          <h2 className="text-3xl font-bold">市場概覽</h2>
          <p className="text-slate-500">監控台股認知差與情緒走勢</p>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="輸入股票代碼 (例如: 2330)"
              className="pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none w-64"
            />
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition disabled:bg-slate-400 flex items-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? "分析中..." : "分析"}
          </button>
        </div>
      </header>

      {sentimentData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card
            title="市場情緒 Z-Score"
            value={sentimentData.z_score.toFixed(2)}
            status={Math.abs(sentimentData.z_score) > 2 ? "Warning" : "Success"}
            description={sentimentData.alert}
            icon={<TrendingUp className={`w-5 h-5 ${Math.abs(sentimentData.z_score) > 2 ? 'text-amber-500' : 'text-green-500'}`} />}
          />
          <Card
            title="認知差狀態"
            value={sentimentData.divergence === "Retail_Trap" ? "散戶接盤" : sentimentData.divergence === "Professional_Layout" ? "專業佈局" : "中立"}
            status={sentimentData.divergence === "Retail_Trap" ? "Danger" : sentimentData.divergence === "Professional_Layout" ? "Success" : "Warning"}
            description={sentimentData.divergence === "Retail_Trap" ? "社群看多 vs 法人賣超 $\rightarrow$ 高風險" : "市場情緒與籌碼方向一致"}
            icon={<AlertCircle className={`w-5 h-5 ${sentimentData.divergence === "Retail_Trap" ? 'text-red-500' : 'text-blue-500'}`} />}
          />
          <Card
            title="建議操作"
            value={sentimentData.divergence === "Professional_Layout" ? "可關注" : sentimentData.divergence === "Retail_Trap" ? "謹慎" : "觀察"}
            status={sentimentData.divergence === "Professional_Layout" ? "Success" : sentimentData.divergence === "Retail_Trap" ? "Danger" : "Warning"}
            description="基於情緒與籌碼的初步建議"
            icon={<CheckCircle2 className="w-5 h-5 text-indigo-500" />}
          />
        </div>
      )}

      <div className="bg-white border rounded-xl p-6 shadow-sm">
        <h3 className="text-lg font-bold mb-4">最近的決策追蹤</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b text-slate-400 text-sm">
              <tr>
                <th className="pb-3 font-medium">股票</th>
                <th className="pb-3 font-medium">狀態</th>
                <th className="pb-3 font-medium">信心度</th>
                <th className="pb-3 font-medium">最後更新</th>
                <th className="pb-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              <tr className="border-b hover:bg-slate-50 transition">
                <td className="py-4 font-bold">2330 台積電</td>
                <td className="py-4">
                  <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-600 text-xs">Deep Dive</span>
                </td>
                <td className="py-4">8/10</td>
                <td className="py-4 text-slate-500">2026-10-17</td>
                <td className="py-4">
                  <button className="text-indigo-600 hover:underline">查看詳情</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Card({ title, value, status, description, icon }) {
  const statusColors = {
    Success: "text-green-600 bg-green-50 border-green-100",
    Warning: "text-amber-600 bg-amber-50 border-amber-100",
    Danger: "text-red-600 bg-red-50 border-red-100",
  };

  return (
    <div className={`border rounded-xl p-5 bg-white shadow-sm ${statusColors[status] || ''}`}>
      <div className="flex justify-between items-start mb-4">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        {icon}
      </div>
      <div className="text-3xl font-bold mb-2">{value}</div>
      <p className="text-xs opacity-80">{description}</p>
    </div>
  );
}
