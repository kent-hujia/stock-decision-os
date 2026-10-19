import { Suspense } from 'react';
import TradesPage from '@/components/TradesPage';
import { Loading } from '@/components/ui';

export default function Trades() {
  return (
    <Suspense fallback={<Loading />}>
      <TradesPage />
    </Suspense>
  );
}
