import { Suspense } from 'react';
import NewTradePage from '@/components/NewTradePage';
import { Loading } from '@/components/ui';

export default function NewTrade() {
  return (
    <Suspense fallback={<Loading />}>
      <NewTradePage />
    </Suspense>
  );
}
