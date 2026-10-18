"use client";

import { useState } from 'react';
import { ArrowRight, AlertTriangle, CheckCircle, MessageSquare, ChevronLeft } from 'lucide-react';

type Step = 'Triage' | 'DeepDive' | 'Adversarial' | 'Gate' | 'Completed';

export default function DecisionPage() {
  const [step, setStep] = useState<Step>('Triage');
  const [ticker, setTicker] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [questions, setQuestions] = useState<any[]>([]);
  const [rebuttals, setRebuttals] = useState<any>({});
  const [loading, setLoading] = useState(false);

  const startDecision = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/decision/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'user-123', ticker }),
      });
      const data = await res.json();
      // We would store this ID in state/context
      setStep('DeepDive');
    } catch (e) {
      alert("啟動決策失敗");
    } finally {
      setLoading(false);
    }
  };

  const generateQuestions = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/decision/some-id/adversarial/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hypothesis }),
      });
      const data = await res.json();
      setQuestions(data.questions);
      setStep('Adversarial');
    } catch (e) {
      alert("AI 質詢生成失敗");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center gap-4 mb-8">
        <ChevronLeft className="cursor-pointer hover:text-indigo-600" />
        <h1 className="text-2xl font-bold">投資決策管線</h1>
      </div>

      {/* Progress Bar */}
      <div className="flex justify-between items-center relative mb-12">
        <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-200 -z-10 transform -translate-y-1/2"></div>
        {['Triage', 'DeepDive', 'Adversarial', 'Gate', 'Completed'].map((s, i) => (
          <div
            key={s}
            className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-colors ${
              step === s ? 'bg-indigo-600 text-white scale-125' :
              (i < ['Triage', 'DeepDive', 'Adversarial', 'Gate', 'Completed'].indexOf(step)) ? 'bg-green-500 text-white' : 'bg-white border text-slate-400'
            }`}
          >
            {i + 1}
          </div>
        ))}
      </div>

      {/* Content Area */}
      <div className="bg-white border rounded-2xl p-8 shadow-sm min-h-[400px]">
        {step === 'Triage' && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold">第一階段：快速篩選 (Triage)</h3>
            <p className="text-slate-500">在進入深度分析前，請先確認個股基本條件。</p>
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 border rounded-lg hover:bg-slate-50 cursor-pointer">
                <CheckCircle className="w-5 h-5 text-slate-300" />
                <span>營收趨勢為正 (YoY &gt; 0%)</span>
              </div>
              <div className="flex items-center gap-3 p-4 border rounded-lg hover:bg-slate-50 cursor-pointer">
                <CheckCircle className="w-5 h-5 text-slate-300" />
                <span>法人籌碼未出現集體出逃</span>
              </div>
              <div className="flex items-center gap-3 p-4 border rounded-lg hover:bg-slate-50 cursor-pointer">
                <CheckCircle className="w-5 h-5 text-slate-300" />
                <span>價格處於合理區間 (非極端追高)</span>
              </div>
            </div>
            <div className="flex gap-4 mt-8">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="輸入股票代碼 (例如: 2330)"
                className="flex-1 px-4 py-2 border rounded-lg outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                onClick={startDecision}
                disabled={loading || !ticker}
                className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:bg-slate-400 transition"
              >
                {loading ? "啟動中..." : "進入深度分析"}
              </button>
            </div>
          </div>
        )}

        {step === 'DeepDive' && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold">第二階段：深度分析 (Deep Dive)</h3>
            <p className="text-slate-500">請詳細描述您的投資假設。這將成為後續 AI 質詢的基礎。</p>
            <div className="space-y-4">
              <label className="block text-sm font-medium text-slate-700">投資假設 (Thesis)</label>
              <textarea
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="例如：預期 AI 伺服器需求將在明年 Q1 爆發，帶動營收增長 30%，且目前法人僅少量布局..."
                className="w-full h-40 p-4 border rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button
              onClick={generateQuestions}
              disabled={loading || !hypothesis}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:bg-slate-400 transition flex items-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              <span>觸發對抗性審查</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {step === 'Adversarial' && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-xl font-bold">第三階段：對抗性審查 (Adversarial Review)</h3>
            </div>
            <p className="text-slate-500"> AI 空頭已對您的假設提出質詢。請提供充分理由反駁，否則將無法買入。</p>

            <div className="space-y-6">
              {questions.length === 0 ? (
                <div className="text-center py-12 text-slate-400">生成中...</div>
              ) : (
                questions.map((q) => (
                  <div key={q.id} className="p-6 border rounded-xl bg-slate-50 space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold uppercase px-2 py-1 bg-red-100 text-red-600 rounded">{q.risk_type} 風險</span>
                      <MessageSquare className="w-4 h-4 text-slate-400" />
                    </div>
                    <p className="font-medium text-slate-800">{q.question}</p>
                    <textarea
                      placeholder="請輸入您的反駁理由..."
                      className="w-full p-3 border rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 h-24"
                      onChange={(e) => setRebuttals({...rebuttals, [q.id]: e.target.value})}
                    />
                  </div>
                ))
              )}
            </div>

            <button
              onClick={() => setStep('Gate')}
              disabled={Object.keys(rebuttals).length < questions.length}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:bg-slate-400 transition"
            >
              提交審查並進入買入閘門
            </button>
          </div>
        )}

        {step === 'Gate' && (
          <div className="space-y-6 text-center py-12">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-2xl font-bold">最終買入閘門</h3>
            <p className="text-slate-500 max-w-md mx-auto">
              您已完成所有邏輯審查。請最後一次確認您的止損點與目標價，確保不再受情緒干擾。
            </p>
            <div className="flex justify-center gap-4 mt-8">
              <button onClick={() => setStep('Completed')} className="bg-green-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-green-700 transition">
                確認買入 $\rightarrow$ 啟動監控
              </button>
            </div>
          </div>
        )}

        {step === 'Completed' && (
          <div className="text-center py-12">
            <h3 className="text-2xl font-bold mb-4">決策已完成！</h3>
            <p className="text-slate-500 mb-8">系統已將您的投資假設轉化為監控指標。若發生失效事件，我們將立即通知您。</p>
            <button
              onClick={() => window.location.href = '/'}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition"
            >
              返回儀表板
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Loader2({ className }: { className?: string }) {
  return <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56" /><polyline points="22 4 22 10 12 10" /></svg>;
}
