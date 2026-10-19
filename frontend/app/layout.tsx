import './globals.css'
import { Suspense } from 'react'
import type { Metadata } from 'next'
import Nav from '@/components/Nav'

export const metadata: Metadata = {
  title: 'Stock Decision OS',
  description: '台股波段練習：籌碼與技術檢查、模擬交易與檢討、營收品質分析，資料來自 FinMind 公開資料。',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-TW">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <nav className="border-b bg-white">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap gap-2 justify-between items-center">
            <a href="/" className="text-lg font-bold text-indigo-600">Stock Decision OS</a>
            <Suspense>
              <Nav />
            </Suspense>
          </div>
        </nav>
        <main className="px-4 sm:px-6 py-6 max-w-6xl mx-auto">
          {children}
        </main>
        <footer className="max-w-6xl mx-auto px-4 sm:px-6 pb-8 text-xs text-slate-400">
          資料來源：FinMind（台灣證券交易所、櫃買中心、公開資訊觀測站公開資料）。本網站內容僅供研究參考，不構成投資建議。
        </footer>
      </body>
    </html>
  )
}
