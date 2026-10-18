import { Suspense } from 'react';
import DecisionsPage from '@/components/DecisionsPage';
import { Loading } from '@/components/ui';

export default function Decisions() {
  return (
    <Suspense fallback={<Loading />}>
      <DecisionsPage />
    </Suspense>
  );
}
