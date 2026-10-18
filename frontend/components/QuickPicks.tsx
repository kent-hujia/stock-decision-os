import Link from 'next/link';

const PICKS = [
  ['2330', '台積電'],
  ['2317', '鴻海'],
  ['2454', '聯發科'],
  ['2412', '中華電'],
  ['2308', '台達電'],
];

export default function QuickPicks({ basePath, intro }: { basePath: string; intro: string }) {
  return (
    <div className="bg-white border border-dashed border-slate-300 rounded-xl px-6 py-12 text-center space-y-4">
      <p className="text-slate-600">{intro}</p>
      <div className="flex flex-wrap justify-center gap-2">
        {PICKS.map(([id, name]) => (
          <Link key={id} href={`${basePath}?ticker=${id}`}
            className="px-3 py-1.5 rounded-full border border-slate-300 text-sm hover:border-indigo-400 hover:text-indigo-700">
            {id} {name}
          </Link>
        ))}
      </div>
    </div>
  );
}
