'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Warehouse,
  Boxes,
  PackageCheck,
  Layers,
  Armchair,
  Factory,
  Users,
  ShoppingCart,
  Truck,
  Banknote,
  TrendingUp,
  FileText,
  Sparkles,
  Settings,
  Menu,
  X,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeVariant?: 'default' | 'warning' | 'danger';
}

const navItems: NavItem[] = [
  { name: 'Панель управления', href: '/', icon: LayoutDashboard },
  { name: 'Склады (Обзор)', href: '/warehouses', icon: Warehouse },
  { name: 'Склад №1 — Сырье', href: '/warehouses/wh-1', icon: Boxes },
  { name: 'Склад №2 — Продукция', href: '/warehouses/wh-2', icon: PackageCheck },
  { name: 'Материалы', href: '/materials', icon: Layers, badge: '3', badgeVariant: 'warning' },
  { name: 'Каталог изделий', href: '/products', icon: Armchair },
  { name: 'Производство', href: '/production', icon: Factory, badge: '2 активных' },
  { name: 'Сотрудники', href: '/employees', icon: Users },
  { name: 'Продажи & CRM', href: '/sales', icon: ShoppingCart },
  { name: 'Поставщики', href: '/suppliers', icon: Truck },
  { name: 'Финансы', href: '/finance', icon: Banknote },
  { name: 'Аналитика', href: '/analytics', icon: TrendingUp },
  { name: 'Отчеты', href: '/reports', icon: FileText },
  { name: 'AI Ассистент', href: '/ai-assistant', icon: Sparkles, badge: 'AI' },
  { name: 'Настройки', href: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const [isOpenMobile, setIsOpenMobile] = useState(false);

  return (
    <>
      {/* Mobile hamburger button */}
      <div className="lg:hidden fixed top-3 left-3 z-50">
        <button
          onClick={() => setIsOpenMobile(!isOpenMobile)}
          className="p-2 rounded-lg bg-furni-primary text-white shadow-md focus:outline-none"
        >
          {isOpenMobile ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Overlay for mobile */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsOpenMobile(false)}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 w-64 bg-furni-primary text-white flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 border-r border-[#1e4841]',
          isOpenMobile ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-[#214f44] flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center font-bold text-lg text-emerald-300 shadow-inner group-hover:scale-105 transition-transform">
              FC
            </div>
            <div>
              <div className="font-bold text-lg tracking-tight flex items-center gap-1.5">
                <span>FurniCore</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.2 rounded font-mono">
                  ERP
                </span>
              </div>
              <div className="text-xs text-stone-300">Мебельное производство</div>
            </div>
          </Link>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-stone-400 uppercase">
            Основное меню
          </div>
          {navItems.map((item) => {
            const isActive =
              item.href === '/'
                ? pathname === '/'
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpenMobile(false)}
                className={cn(
                  'flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all group select-none',
                  isActive
                    ? 'bg-furni-secondary text-white shadow-sm font-semibold'
                    : 'text-stone-300 hover:text-white hover:bg-white/5',
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={cn(
                      'w-4 h-4 shrink-0 transition-colors',
                      isActive ? 'text-emerald-300' : 'text-stone-400 group-hover:text-stone-200',
                    )}
                  />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold',
                      item.badgeVariant === 'warning'
                        ? 'bg-amber-500/30 text-amber-200 border border-amber-500/40'
                        : item.badgeVariant === 'danger'
                        ? 'bg-rose-500/30 text-rose-200 border border-rose-500/40'
                        : 'bg-white/10 text-stone-200 border border-white/10',
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>

        {/* Bottom User status */}
        <div className="p-4 border-t border-[#214f44] bg-[#122e29]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-emerald-600/30 border border-emerald-500/50 flex items-center justify-center text-xs font-bold text-emerald-200">
                АС
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-white truncate">Арман Серикович</div>
                <div className="text-[11px] text-emerald-300 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Владелец (Owner)</span>
                </div>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        </div>
      </aside>
    </>
  );
};
