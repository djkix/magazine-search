import type { ReactNode } from "react";

export default function PageContainer({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto max-w-6xl px-4 py-8 lg:px-8 ${className}`}>{children}</div>;
}
