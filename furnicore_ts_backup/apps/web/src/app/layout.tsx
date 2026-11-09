import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';

export const metadata: Metadata = {
  title: 'FurniCore ERP — Управление мебельным производством',
  description: 'Профессиональная ERP система для мебельного предприятия: два склада, производство, CRM, учет и аналитика в KZT',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-furni-bg text-furni-text antialiased">
        <Sidebar />
        <div className="lg:pl-64 flex flex-col min-h-screen">
          <Header />
          <main className="flex-1 p-6 max-w-7xl w-full mx-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
