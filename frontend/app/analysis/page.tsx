"use client";

import { useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, Loader2, Search } from 'lucide-react';

export default function RevenueXRayPage() {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);

  const handleAnalyze = async () => {
    if (!ticker) return;
    setLoading(true);
    try {
      // 1. Trigger Analysis
      await fetch(`http://localhost:8000/api/v1/revenue/${ticker}/analyze`, { method: 'POST' });

      // 2. Poll for result (Simple polling for MVP)
      let result = null;
      while (!result) {
        const res = await fetch(`http://localhost:8000/api/v1/revenue/${ticker}`);
        if (res.ok) {
          result = await res.json();
        } else {
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
      }
      setData(result);
    } catch (e) {
      alert("分析失敗，請稍後再試");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <header className="flex justify-between items-end">
        <div className="space-y-2">
          <h2 className="text-3xl font-bold">營收 X 光分析</h2>
          <p className="text-slate-500">深度拆解財報文本，辨識成長含金量</p>
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
            {loading ? "分析中..." : "啟動 X 光分析"}
          </button>
        </div>
      </header>

      {data && (
        <div className="space-y-6">
          {/* Quality Score Card */}
          <div className="bg-white border rounded-2xl p-8 shadow-sm flex items-center justify-between">
            <div className="space-y-2">
              <h3 className="text-xl font-bold">營收含金量得分</h3>
              <p className="text-slate-500">基於 AI 對 MD&A 文本之拆解與陷阱偵測結果</p>
            </div>
            <div className="text-6xl font-black text-indigo-600">{data.quality_score}%</div>
          </div>

          {/* Storyline Visualization */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border rounded-2xl p-6 shadow-sm space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Activity className="w-5 h-5 text-indigo-500" />
                成長路徑拆解
              </h3>
              <div className="space-y-4">
                {data.story_line.map((path: any, i: number) => (
                  <div key={i} className={`p-4 border rounded-xl flex gap-4 ${
                    path.type === 'green' ? 'bg-green-50 border-green-100' :
                    path.type === 'red' ? 'bg-red-50 border-red-100' : 'bg-yellow-50 border-yellow-100'
                  }`}>
                    <div className={`w-2 h-12 rounded-full ${
                      path.type === 'green' ? 'bg-green-500' :
                      path.type === 'red' ? 'bg-red-500' : 'bg-yellow-500'
                    }`} />
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase">{path.type} Path</span>
                        <span className="text-sm font-medium">{path.amount}</span>
                      </div>
                      <p className="text-sm text-slate-600">{path.evidence}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white border rounded-2xl p-6 shadow-sm space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-500" />
                營收陷阱偵測
              </h3>
              <div className="space-y-4">
                {data.traps && data.traps.length > 0 ? (
                  data.traps.map((trap: any, i: number) => (
                    <div key={i} className="p-4 border border-red-100 bg-red-50 rounded-xl flex gap-4 items-start">
                      <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold text-red-700 text-sm">{trap.type}</span>
                        <p className="text-sm text-red-600">{trap.desc}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center gap-2 text-green-600 p-4 bg-green-50 border border-green-100 rounded-xl">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-medium">未偵測到明顯營收陷阱</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
