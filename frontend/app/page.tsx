import { Suspense } from 'react';
import OverviewPage from '@/components/OverviewPage';
import { Loading } from '@/components/ui';

export default function Home() {
  return (
    <Suspense fallback={<Loading />}>
      <OverviewPage />
    </Suspense>
  );
}
