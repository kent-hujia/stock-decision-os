import './globals.css'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-TW">
      <body className={`${inter.className} bg-slate-50 text-slate-900`}>
        <nav className="border-b bg-white px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-indigo-600">Stock Decision OS</h1>
          <div className="space-x-4 text-sm font-medium">
            <a href="/" className="hover:text-indigo-600">儀表板</a>
            <a href="/decision" className="hover:text-indigo-600">新決策</a>
            <a href="/analysis" className="hover:text-indigo-600">營收分析</a>
          </div>
        </nav>
        <main className="p-6 max-w-7xl mx-auto">
          {children}
        </main>
      </body>
    </html>
  )
}
