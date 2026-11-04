'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  PackageCheck,
  ArrowDownLeft,
  ArrowUpRight,
  Search,
  Filter,
  ChevronLeft,
  CheckCircle2,
  Lock,
  Truck,
  Plus,
  ShieldCheck,
  Tag,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT } from '@/lib/utils';

const initialFinishedGoods = [
  {
    id: '1',
    sku: 'PRD-WRD-001',
    name: 'Шкаф 3-дверный "Nordic Loft" с зеркалом',
    category: 'Шкафы',
    dimensions: '2200x1500x600 мм',
    currentStock: 6,
    reservedStock: 2,
    availableStock: 4,
    productionCostKZT: 145000,
    salePriceKZT: 265000,
    totalValuationKZT: 870000, // based on production cost
    location: 'Ряд 1, Место 04',
    status: 'AVAILABLE',
  },
  {
    id: '2',
    sku: 'PRD-TBL-001',
    name: 'Стол обеденный "Almaty Oak" раскладной',
    category: 'Столы',
    dimensions: '1600(2100)x900x760 мм',
    currentStock: 12,
    reservedStock: 3,
    availableStock: 9,
    productionCostKZT: 98000,
    salePriceKZT: 185000,
    totalValuationKZT: 1176000,
    location: 'Ряд 2, Место 01',
    status: 'AVAILABLE',
  },
  {
    id: '3',
    sku: 'PRD-BED-001',
    name: 'Кровать двуспальная "Comfort Prime 180"',
    category: 'Кровати',
    dimensions: '2150x1920x1100 мм',
    currentStock: 4,
    reservedStock: 1,
    availableStock: 3,
    productionCostKZT: 165000,
    salePriceKZT: 310000,
    totalValuationKZT: 660000,
    location: 'Ряд 3, Место 02',
    status: 'AVAILABLE',
  },
  {
    id: '4',
    sku: 'PRD-KTC-001',
    name: 'Кухонный гарнитур угловой "Astana Mod" 3.2м',
    category: 'Кухни',
    dimensions: '3200x1800x2300 мм',
    currentStock: 2,
    reservedStock: 1,
    availableStock: 1,
    productionCostKZT: 420000,
    salePriceKZT: 780000,
    totalValuationKZT: 840000,
    location: 'Секция К-1',
    status: 'AVAILABLE',
  },
  {
    id: '5',
    sku: 'PRD-SOF-001',
    name: 'Диван 3-местный прямой "Nomad Lounge"',
    category: 'Диваны',
    dimensions: '2350x1050x880 мм',
    currentStock: 5,
    reservedStock: 0,
    availableStock: 5,
    productionCostKZT: 175000,
    salePriceKZT: 340000,
    totalValuationKZT: 875000,
    location: 'Ряд 4, Место 05',
    status: 'AVAILABLE',
  },
];

export default function WarehouseTwoPage() {
  const [goods, setGoods] = useState(initialFinishedGoods);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Все');
  const [showShipmentModal, setShowShipmentModal] = useState(false);
  const [selectedSku, setSelectedSku] = useState(initialFinishedGoods[0].sku);
  const [shipmentQty, setShipmentQty] = useState('1');
  const [customerOrderRef, setCustomerOrderRef] = useState('ORD-2026-0089');
  const [toastMessage, setToastMessage] = useState('');

  const categories = ['Все', 'Шкафы', 'Столы', 'Кровати', 'Кухни', 'Диваны'];

  const filteredGoods = goods.filter((g) => {
    const matchesCategory = selectedCategory === 'Все' || g.category === selectedCategory;
    const matchesSearch =
      g.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      g.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      g.dimensions.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const totalInStock = goods.reduce((acc, curr) => acc + curr.currentStock, 0);
  const totalReserved = goods.reduce((acc, curr) => acc + curr.reservedStock, 0);
  const totalAvailable = goods.reduce((acc, curr) => acc + curr.availableStock, 0);
  const totalValuation = goods.reduce((acc, curr) => acc + curr.totalValuationKZT, 0);

  const handleShipment = (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseInt(shipmentQty, 10);
    if (!qty || qty <= 0) return;

    const target = goods.find((g) => g.sku === selectedSku);
    if (!target) return;

    if (target.currentStock < qty) {
      alert(`Ошибка: Недостаточно на складе! В наличии всего ${target.currentStock} шт.`);
      return;
    }

    setGoods((prev) =>
      prev.map((g) => {
        if (g.sku === selectedSku) {
          const newCurrent = g.currentStock - qty;
          const newReserved = Math.max(0, g.reservedStock - qty);
          const newAvailable = newCurrent - newReserved;
          return {
            ...g,
            currentStock: newCurrent,
            reservedStock: newReserved,
            availableStock: newAvailable,
            totalValuationKZT: newCurrent * g.productionCostKZT,
          };
        }
        return g;
      }),
    );

    setShowShipmentModal(false);
    setToastMessage(`Успешная отгрузка: ${qty} шт. переданы по заказу ${customerOrderRef}`);
    setTimeout(() => setToastMessage(''), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 bg-emerald-700 text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-2 text-sm font-medium animate-in fade-in slide-in-from-top duration-300">
          <CheckCircle2 className="w-5 h-5 text-emerald-300" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header and navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-furni-muted mb-1">
            <Link href="/warehouses" className="hover:underline flex items-center gap-1">
              <ChevronLeft className="w-3.5 h-3.5" /> Склады
            </Link>
            <span>/</span>
            <span className="font-medium text-furni-text">Склад №2</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-furni-text">
              Склад №2 — Готовая продукция
            </h1>
            <Badge variant="success">WH-2</Badge>
          </div>
          <p className="text-xs text-furni-muted mt-0.5">
            Зона приемки готовой мебели из цеха, контроль клиентских резервов и отгрузка покупателям
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            icon={<ArrowDownLeft className="w-4 h-4" />}
            onClick={() => alert('Приемка мебели регистрируется при завершении наряда цеха')}
          >
            Приемка из цеха (ОТК)
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Truck className="w-4 h-4" />}
            onClick={() => setShowShipmentModal(true)}
          >
            Отгрузить клиенту
          </Button>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-furni-muted">Всего готовых изделий</div>
          <div className="text-xl font-bold text-furni-text mt-1">{totalInStock} единиц</div>
          <div className="text-[11px] text-emerald-600 mt-1">5 основных категорий</div>
        </Card>

        <Card className="p-4 bg-blue-50/50 border-blue-200">
          <div className="text-xs text-blue-800 font-medium">В резерве под клиентов</div>
          <div className="text-xl font-bold text-blue-700 mt-1">{totalReserved} единиц</div>
          <div className="text-[11px] text-blue-600 mt-1">Ожидают согласованной даты доставки</div>
        </Card>

        <Card className="p-4 bg-emerald-50/50 border-emerald-200">
          <div className="text-xs text-emerald-800 font-medium">Свободно к продаже</div>
          <div className="text-xl font-bold text-emerald-700 mt-1">{totalAvailable} единиц</div>
          <div className="text-[11px] text-emerald-600 mt-1">Доступно для моментального резерва</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-furni-muted">Оценка склада (Себестоимость)</div>
          <div className="text-xl font-bold text-furni-primary mt-1">
            {formatKZT(totalValuation)}
          </div>
          <div className="text-[11px] text-furni-muted mt-1">
            Розничная стоимость: ~{formatKZT(totalValuation * 1.8)}
          </div>
        </Card>
      </div>

      {/* Search and Category Tabs */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  selectedCategory === cat
                    ? 'bg-furni-primary text-white shadow-sm font-semibold'
                    : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-stone-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Поиск по модели, SKU, габаритам..."
              className="w-full pl-9 pr-3 py-1.5 bg-furni-bg rounded-lg border border-furni-border text-xs focus:outline-none focus:ring-2 focus:ring-furni-primary/20"
            />
          </div>
        </div>
      </Card>

      {/* Finished Goods Table */}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#FAFBF9] border-b border-furni-border">
              <tr className="text-furni-muted font-semibold">
                <th className="py-3 px-4">SKU</th>
                <th className="py-3 px-4">Наименование изделия</th>
                <th className="py-3 px-4">Категория</th>
                <th className="py-3 px-4">Габариты (ДxШxВ)</th>
                <th className="py-3 px-4">Локация</th>
                <th className="py-3 px-4 text-center">Всего на складе</th>
                <th className="py-3 px-4 text-center">В резерве</th>
                <th className="py-3 px-4 text-center">Свободно</th>
                <th className="py-3 px-4 text-right">Себестоимость</th>
                <th className="py-3 px-4 text-right">Розничная цена</th>
                <th className="py-3 px-4 text-center">Действие</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-furni-border-light">
              {filteredGoods.map((item) => (
                <tr key={item.id} className="hover:bg-stone-50/80 transition-colors">
                  <td className="py-3 px-4 font-mono font-medium text-stone-600">{item.sku}</td>
                  <td className="py-3 px-4 font-semibold text-furni-text">
                    {item.name}
                  </td>
                  <td className="py-3 px-4 text-stone-600">{item.category}</td>
                  <td className="py-3 px-4 font-mono text-[11px] text-stone-500">
                    {item.dimensions}
                  </td>
                  <td className="py-3 px-4 text-stone-600">{item.location}</td>
                  <td className="py-3 px-4 text-center font-bold font-mono text-furni-text">
                    {item.currentStock} шт
                  </td>
                  <td className="py-3 px-4 text-center font-mono">
                    {item.reservedStock > 0 ? (
                      <span className="inline-flex items-center gap-1 text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-semibold">
                        <Lock className="w-3 h-3" /> {item.reservedStock} шт
                      </span>
                    ) : (
                      <span className="text-stone-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center font-mono">
                    <span className="inline-flex items-center px-2 py-0.5 rounded font-bold bg-emerald-50 text-emerald-800">
                      {item.availableStock} шт
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-stone-600">
                    {formatKZT(item.productionCostKZT)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono font-bold text-furni-primary">
                    {formatKZT(item.salePriceKZT)}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-[11px] py-1 px-2"
                      onClick={() => {
                        setSelectedSku(item.sku);
                        setShowShipmentModal(true);
                      }}
                    >
                      Отгрузить
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Shipment Modal */}
      {showShipmentModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-furni-border animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-furni-text">
              Отгрузка готовой продукции (Склад №2)
            </h3>
            <p className="text-xs text-furni-muted mt-1">
              Регистрация выдачи клиенту с защитой от повторного списания
            </p>

            <form onSubmit={handleShipment} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Изделие для отгрузки
                </label>
                <select
                  value={selectedSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs bg-white focus:ring-2 focus:ring-furni-primary"
                >
                  {goods.map((g) => (
                    <option key={g.sku} value={g.sku}>
                      {g.sku} — {g.name} (В наличии: {g.currentStock} шт)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Количество (шт)
                </label>
                <input
                  type="number"
                  min="1"
                  required
                  value={shipmentQty}
                  onChange={(e) => setShipmentQty(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs focus:ring-2 focus:ring-furni-primary"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Заказ клиента (Reference Number)
                </label>
                <input
                  type="text"
                  required
                  value={customerOrderRef}
                  onChange={(e) => setCustomerOrderRef(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs focus:ring-2 focus:ring-furni-primary"
                />
              </div>

              <div className="p-3 bg-stone-50 rounded-lg text-xs text-stone-600 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Операция необратима и фиксируется в несгораемом журнале движений.</span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-furni-border-light">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowShipmentModal(false)}
                >
                  Отмена
                </Button>
                <Button type="submit" variant="primary" size="sm">
                  Подтвердить отгрузку
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
