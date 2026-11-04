'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bell,
  Search,
  Warehouse,
  Boxes,
  PackageCheck,
  AlertTriangle,
  Calendar,
  ChevronDown,
} from 'lucide-react';

export const Header: React.FC = () => {
  const pathname = usePathname();

  // Determine current active warehouse view
  let activeWarehouseName = 'Все склады (WH-1 & WH-2)';
  if (pathname.includes('/wh-1')) {
    activeWarehouseName = 'Склад №1 — Сырье и материалы';
  } else if (pathname.includes('/wh-2')) {
    activeWarehouseName = 'Склад №2 — Готовая продукция';
  }

  const currentDate = new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    weekday: 'short',
  }).format(new Date());

  return (
    <header className="h-16 bg-white border-b border-furni-border sticky top-0 z-30 px-6 flex items-center justify-between">
      {/* Left: Warehouse quick selector */}
      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-furni-bg rounded-lg border border-furni-border text-xs font-medium text-furni-text">
          <Warehouse className="w-4 h-4 text-furni-secondary" />
          <span className="font-semibold">{activeWarehouseName}</span>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-furni-muted">
          <Link
            href="/warehouses/wh-1"
            className="px-2 py-1 rounded hover:bg-stone-100 flex items-center gap-1 transition-colors"
          >
            <Boxes className="w-3.5 h-3.5 text-furni-secondary" />
            <span className="hidden md:inline">WH-1 Сырье</span>
          </Link>
          <span className="text-stone-300">•</span>
          <Link
            href="/warehouses/wh-2"
            className="px-2 py-1 rounded hover:bg-stone-100 flex items-center gap-1 transition-colors"
          >
            <PackageCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span className="hidden md:inline">WH-2 Продукция</span>
          </Link>
        </div>
      </div>

      {/* Right side items */}
      <div className="flex items-center gap-3">
        {/* Date display */}
        <div className="hidden lg:flex items-center gap-1.5 text-xs text-furni-muted bg-stone-50 px-2.5 py-1.5 rounded-md border border-stone-200">
          <Calendar className="w-3.5 h-3.5 text-furni-secondary" />
          <span className="capitalize">{currentDate}</span>
        </div>

        {/* Currency badge */}
        <div className="hidden sm:inline-flex items-center px-2 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          Валюта: KZT (₸)
        </div>

        {/* Low-stock notification bell */}
        <Link
          href="/materials?lowStock=true"
          title="3 материала требуют пополнения"
          className="relative p-2 rounded-lg text-furni-muted hover:text-furni-text hover:bg-stone-100 transition-colors"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-500 animate-ping" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-500" />
        </Link>
      </div>
    </header>
  );
};
