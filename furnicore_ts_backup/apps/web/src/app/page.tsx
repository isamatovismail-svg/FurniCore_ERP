'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  Boxes,
  PackageCheck,
  Factory,
  ShoppingCart,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Calendar,
  Layers,
  ChevronRight,
  Clock,
  Sparkles,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT, formatNumber } from '@/lib/utils';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts';

// Realistic financial and operational demo metrics (in KZT)
const metrics = {
  totalRevenueKZT: 12450000,
  revenueChangePercent: +14.2,
  grossProfitKZT: 6850000,
  grossProfitMargin: 55.0,
  netProfitKZT: 5030000,
  netProfitMargin: 40.4,
  totalExpensesKZT: 7420000,
  rawMaterialsCount: 16,
  rawMaterialStockValueKZT: 14250000,
  finishedProductsCount: 29,
  finishedProductsStockValueKZT: 8450000,
  activeProductionOrders: 4,
  pendingCustomerOrders: 3,
  lowStockAlertsCount: 3,
};

const financialTrend = [
  { month: 'Июн', выручка: 7800000, расходы: 5400000, прибыль: 2400000 },
  { month: 'Июл', выручка: 8400000, расходы: 5800000, прибыль: 2600000 },
  { month: 'Авг', выручка: 9100000, расходы: 6100000, прибыль: 3000000 },
  { month: 'Сен', выручка: 10500000, расходы: 6700000, прибыль: 3800000 },
  { month: 'Окт', выручка: 11200000, расходы: 7100000, прибыль: 4100000 },
  { month: 'Ноя (тек)', выручка: 12450000, расходы: 7420000, прибыль: 5030000 },
];

const categoryData = [
  { category: 'Шкафы', выпущено: 18, сумма: 4770000 },
  { category: 'Кухни', выпущено: 6, сумма: 4680000 },
  { category: 'Столы', выпущено: 24, сумма: 4440000 },
  { category: 'Кровати', выпущено: 14, сумма: 4340000 },
  { category: 'Диваны', выпущено: 9, сумма: 3060000 },
];

const lowStockItems = [
  {
    sku: 'MAT-CHP-001',
    name: 'ЛДСП Egger Дуб Галифакс 18мм',
    current: 32,
    min: 50,
    unit: 'лист',
    deficiency: 18,
  },
  {
    sku: 'MAT-HND-001',
    name: 'Ручка профильная 160мм Черная',
    current: 80,
    min: 100,
    unit: 'шт',
    deficiency: 20,
  },
  {
    sku: 'MAT-FOM-001',
    name: 'Поролон HR 3535 (100мм)',
    current: 15,
    min: 20,
    unit: 'лист',
    deficiency: 5,
  },
];

const recentMovements = [
  {
    id: '1',
    code: 'MOV-2026-0091',
    type: 'RECEIPT',
    typeLabel: 'Поступление',
    warehouse: 'Склад №1 (Сырье)',
    item: 'Массив дуба 50мм калиброванный',
    qty: '12.5 м³',
    sumKZT: 4750000,
    time: 'Сегодня, 14:30',
  },
  {
    id: '2',
    code: 'MOV-2026-0090',
    type: 'RECEIPT',
    typeLabel: 'Выпуск из цеха',
    warehouse: 'Склад №2 (Продукция)',
    item: 'Шкаф 3-дверный "Nordic Loft"',
    qty: '2 шт',
    sumKZT: 530000,
    time: 'Сегодня, 11:15',
  },
  {
    id: '3',
    code: 'MOV-2026-0089',
    type: 'ISSUE',
    typeLabel: 'Отпуск в цех',
    warehouse: 'Склад №1 (Сырье)',
    item: 'МДФ влагостойкий 16мм',
    qty: '10 листов',
    sumKZT: 142000,
    time: 'Вчера, 16:45',
  },
  {
    id: '4',
    code: 'MOV-2026-0088',
    type: 'SHIPMENT',
    typeLabel: 'Отгрузка клиенту',
    warehouse: 'Склад №2 (Продукция)',
    item: 'Кухонный гарнитур "Astana Mod"',
    qty: '1 компл',
    sumKZT: 780000,
    time: 'Вчера, 10:20',
  },
];

export default function DashboardPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('Месяц');

  const periods = ['Сегодня', 'Вчера', 'Неделя', 'Месяц', 'Год', 'Период'];

  return (
    <div className="space-y-6">
      {/* Top Banner & Date Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-furni-text">
            Панель управления FurniCore
          </h1>
          <p className="text-sm text-furni-muted mt-0.5">
            Операционный и финансовый мониторинг мебельной фабрики в режиме реального времени
          </p>
        </div>

        {/* Date Filter Pills */}
        <div className="flex items-center bg-white p-1 rounded-xl border border-furni-border shadow-sm">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setSelectedPeriod(p)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                selectedPeriod === p
                  ? 'bg-furni-primary text-white shadow-sm font-semibold'
                  : 'text-furni-muted hover:text-furni-text hover:bg-stone-50'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Primary Financial KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Revenue */}
        <Card className="hover:shadow-card-hover transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-furni-muted uppercase tracking-wider">
              Выручка от продаж
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold text-sm">
              ₸
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-furni-text">
              {formatKZT(metrics.totalRevenueKZT)}
            </div>
            <div className="flex items-center gap-1.5 mt-2 text-xs font-medium text-emerald-600">
              <ArrowUpRight className="w-3.5 h-3.5" />
              <span>+{metrics.revenueChangePercent}% к прошлому периоду</span>
            </div>
          </div>
        </Card>

        {/* Gross Profit */}
        <Card className="hover:shadow-card-hover transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-furni-muted uppercase tracking-wider">
              Валовая прибыль
            </span>
            <span className="text-xs font-mono bg-stone-100 text-stone-700 px-2 py-0.5 rounded">
              Маржа {metrics.grossProfitMargin}%
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-emerald-800">
              {formatKZT(metrics.grossProfitKZT)}
            </div>
            <div className="text-xs text-furni-muted mt-2">
              Выручка за вычетом себестоимости материалов
            </div>
          </div>
        </Card>

        {/* Net Profit */}
        <Card className="hover:shadow-card-hover transition-shadow bg-gradient-to-br from-white to-[#f0f6f3]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-furni-secondary uppercase tracking-wider">
              Чистая прибыль (EBIT)
            </span>
            <span className="text-xs font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-bold">
              {metrics.netProfitMargin}%
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-furni-primary">
              {formatKZT(metrics.netProfitKZT)}
            </div>
            <div className="text-xs text-furni-muted mt-2">
              После вычета операционных расходов и ФОТ
            </div>
          </div>
        </Card>

        {/* Total Expenses */}
        <Card className="hover:shadow-card-hover transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-furni-muted uppercase tracking-wider">
              Операционные расходы
            </span>
            <span className="text-xs font-mono text-rose-600 bg-rose-50 px-2 py-0.5 rounded">
              ФОТ, аренда, свет
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-stone-800">
              {formatKZT(metrics.totalExpensesKZT)}
            </div>
            <div className="text-xs text-furni-muted mt-2">
              Аренда, станки, логистика, зарплата
            </div>
          </div>
        </Card>
      </div>

      {/* TWO WAREHOUSES OVERVIEW (Prominently featured per prompt requirement) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Warehouse 1: Raw Materials */}
        <Card className="border-l-4 border-l-amber-600 bg-white">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-800 flex items-center justify-center">
                <Boxes className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-base text-furni-text">
                    Склад №1 — Сырье и материалы
                  </h3>
                  <Badge variant="warning">WH-1</Badge>
                </div>
                <p className="text-xs text-furni-muted mt-0.5">
                  Плитные материалы, массив дерева, фурнитура, ЛКМ, ткани
                </p>
              </div>
            </div>
            <Link href="/warehouses/wh-1">
              <Button variant="outline" size="sm">
                Открыть <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-5 pt-4 border-t border-furni-border-light text-center">
            <div className="p-2.5 bg-furni-bg rounded-lg">
              <div className="text-xs text-furni-muted">Оценка запасов</div>
              <div className="text-base font-bold text-furni-primary mt-1">
                {formatKZT(metrics.rawMaterialStockValueKZT)}
              </div>
            </div>
            <div className="p-2.5 bg-furni-bg rounded-lg">
              <div className="text-xs text-furni-muted">Позиций на складе</div>
              <div className="text-base font-bold text-furni-text mt-1">
                {metrics.rawMaterialsCount} SKU
              </div>
            </div>
            <div className="p-2.5 bg-amber-50/60 rounded-lg">
              <div className="text-xs text-amber-800 font-medium">Ниже минимума</div>
              <div className="text-base font-bold text-amber-700 mt-1">
                {metrics.lowStockAlertsCount} позиции
              </div>
            </div>
          </div>
        </Card>

        {/* Warehouse 2: Finished Products */}
        <Card className="border-l-4 border-l-emerald-600 bg-white">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-800 flex items-center justify-center">
                <PackageCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-base text-furni-text">
                    Склад №2 — Готовая продукция
                  </h3>
                  <Badge variant="success">WH-2</Badge>
                </div>
                <p className="text-xs text-furni-muted mt-0.5">
                  Шкафы, столы, кровати, кухни, диваны (свободные и в резерве)
                </p>
              </div>
            </div>
            <Link href="/warehouses/wh-2">
              <Button variant="outline" size="sm">
                Открыть <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-5 pt-4 border-t border-furni-border-light text-center">
            <div className="p-2.5 bg-furni-bg rounded-lg">
              <div className="text-xs text-furni-muted">Оценка на складе</div>
              <div className="text-base font-bold text-emerald-800 mt-1">
                {formatKZT(metrics.finishedProductsStockValueKZT)}
              </div>
            </div>
            <div className="p-2.5 bg-furni-bg rounded-lg">
              <div className="text-xs text-furni-muted">Готовых единиц</div>
              <div className="text-base font-bold text-furni-text mt-1">
                {metrics.finishedProductsCount} шт
              </div>
            </div>
            <div className="p-2.5 bg-blue-50/60 rounded-lg">
              <div className="text-xs text-blue-800 font-medium">В резерве клиентов</div>
              <div className="text-base font-bold text-blue-700 mt-1">7 единиц</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Financial Charts & Category Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Main Revenue vs Expense Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Динамика выручки, расходов и чистой прибыли (KZT)</CardTitle>
              <p className="text-xs text-furni-muted mt-1">
                Помесячный учет реальных поступлений и производственных затрат
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-emerald-600 inline-block" />
                <span>Выручка</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-stone-400 inline-block" />
                <span>Расходы</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-furni-primary inline-block" />
                <span>Прибыль</span>
              </div>
            </div>
          </CardHeader>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={financialTrend} margin={{ top: 10, right: 10, left: 15, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#173B35" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#173B35" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
                <XAxis dataKey="month" stroke="#6B7280" fontSize={11} />
                <YAxis
                  stroke="#6B7280"
                  fontSize={11}
                  tickFormatter={(val) => `${val / 1000000}M ₸`}
                />
                <Tooltip
                  formatter={(val: any) => [formatKZT(Number(val)), '']}
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    border: '1px solid #E5E7EB',
                    boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="выручка"
                  stroke="#10B981"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorRev)"
                />
                <Area
                  type="monotone"
                  dataKey="прибыль"
                  stroke="#173B35"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorProfit)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Manufacturing Breakdown by Category */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Выпуск по категориям мебели</CardTitle>
              <p className="text-xs text-furni-muted mt-1">Доля производства за месяц</p>
            </div>
          </CardHeader>

          <div className="space-y-4">
            {categoryData.map((cat) => {
              const totalAmount = categoryData.reduce((acc, curr) => acc + curr.сумма, 0);
              const percentage = Math.round((cat.сумма / totalAmount) * 100);

              return (
                <div key={cat.category} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-furni-text">{cat.category}</span>
                    <span className="font-mono text-furni-muted">
                      {cat.выпущено} шт • {formatKZT(cat.сумма)}
                    </span>
                  </div>
                  <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-furni-secondary h-2 rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-5 p-3 rounded-lg bg-emerald-50/70 border border-emerald-200/60 text-xs text-emerald-900 flex items-center justify-between">
            <span className="font-medium">Лидер продаж:</span>
            <span className="font-bold">Шкафы (18 шт / 4.77M ₸)</span>
          </div>
        </Card>
      </div>

      {/* Operational Bottom Section: Low stock alerts & Recent movements */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Low-stock Alerts */}
        <Card className="border-amber-200 bg-[#FFFDF9]">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <CardTitle className="text-amber-900">Дефицит на Складе №1</CardTitle>
            </div>
            <Link href="/materials?lowStock=true">
              <span className="text-xs font-semibold text-amber-700 hover:underline">
                Заказать
              </span>
            </Link>
          </CardHeader>

          <div className="space-y-3">
            {lowStockItems.map((item) => (
              <div
                key={item.sku}
                className="p-3 bg-white rounded-lg border border-amber-200/80 shadow-sm flex items-center justify-between"
              >
                <div>
                  <div className="font-medium text-xs text-stone-900">{item.name}</div>
                  <div className="text-[11px] font-mono text-stone-500 mt-0.5">{item.sku}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-bold text-rose-600">
                    {item.current} {item.unit}
                  </div>
                  <div className="text-[10px] text-stone-400">Мин: {item.min} {item.unit}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <Link href="/warehouses/wh-1">
              <Button variant="outline" size="sm" className="w-full text-xs">
                Оформить приход материалов
              </Button>
            </Link>
          </div>
        </Card>

        {/* Recent Stock Movements */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Журнал складских движений (Аудит)</CardTitle>
              <p className="text-xs text-furni-muted mt-1">
                Транзакционные перемещения между складами и цехом
              </p>
            </div>
            <Link href="/warehouses">
              <Button variant="ghost" size="sm" className="text-xs">
                Все движения <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </Link>
          </CardHeader>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-furni-border-light text-furni-muted pb-2">
                  <th className="pb-2 font-semibold">Код</th>
                  <th className="pb-2 font-semibold">Операция</th>
                  <th className="pb-2 font-semibold">Склад</th>
                  <th className="pb-2 font-semibold">Номенклатура</th>
                  <th className="pb-2 font-semibold">Количество</th>
                  <th className="pb-2 font-semibold text-right">Сумма (KZT)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-furni-border-light">
                {recentMovements.map((m) => (
                  <tr key={m.id} className="hover:bg-stone-50/60 transition-colors">
                    <td className="py-2.5 font-mono text-stone-600 font-medium">{m.code}</td>
                    <td className="py-2.5">
                      <Badge
                        variant={
                          m.type === 'RECEIPT'
                            ? 'success'
                            : m.type === 'SHIPMENT'
                            ? 'info'
                            : 'warning'
                        }
                      >
                        {m.typeLabel}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-stone-700">{m.warehouse}</td>
                    <td className="py-2.5 font-medium text-stone-900">{m.item}</td>
                    <td className="py-2.5 font-mono">{m.qty}</td>
                    <td className="py-2.5 text-right font-bold font-mono text-furni-primary">
                      {formatKZT(m.sumKZT)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
