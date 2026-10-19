import { Suspense } from 'react';
import SwingPage from '@/components/SwingPage';
import { Loading } from '@/components/ui';

export default function Swing() {
  return (
    <Suspense fallback={<Loading />}>
      <SwingPage />
    </Suspense>
  );
}
