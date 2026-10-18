import { Suspense } from 'react';
import XrayPage from '@/components/XrayPage';
import { Loading } from '@/components/ui';

export default function AnalysisPage() {
  return (
    <Suspense fallback={<Loading />}>
      <XrayPage />
    </Suspense>
  );
}
