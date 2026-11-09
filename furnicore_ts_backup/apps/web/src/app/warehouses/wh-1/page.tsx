'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Boxes,
  ArrowDownLeft,
  ArrowUpRight,
  ClipboardList,
  Search,
  Filter,
  AlertTriangle,
  ChevronLeft,
  Plus,
  RefreshCw,
  QrCode,
  CheckCircle2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT, formatNumber } from '@/lib/utils';

// Raw Materials Data on Warehouse 1
const initialMaterials = [
  {
    id: '1',
    sku: 'MAT-WOD-001',
    name: 'Массив дуба 50мм (сухой калиброванный)',
    category: 'Древесина',
    unit: 'м³',
    currentStock: 12.5,
    minStockLevel: 5.0,
    unitCostKZT: 380000,
    totalValueKZT: 4750000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Секция А-1',
  },
  {
    id: '2',
    sku: 'MAT-WOD-002',
    name: 'Массив сосны 40мм обрезной',
    category: 'Древесина',
    unit: 'м³',
    currentStock: 18.0,
    minStockLevel: 8.0,
    unitCostKZT: 145000,
    totalValueKZT: 2610000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Секция А-2',
  },
  {
    id: '3',
    sku: 'MAT-MDF-001',
    name: 'МДФ влагостойкий 16мм Kronospan 2800x2070',
    category: 'Плитные',
    unit: 'лист',
    currentStock: 85,
    minStockLevel: 40,
    unitCostKZT: 14200,
    totalValueKZT: 1207000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Стеллаж В-1',
  },
  {
    id: '4',
    sku: 'MAT-MDF-002',
    name: 'МДФ шлифованный 18мм Kastamonu 2800x2070',
    category: 'Плитные',
    unit: 'лист',
    currentStock: 45,
    minStockLevel: 30,
    unitCostKZT: 16500,
    totalValueKZT: 742500,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Стеллаж В-2',
  },
  {
    id: '5',
    sku: 'MAT-CHP-001',
    name: 'ЛДСП Egger Дуб Галифакс натуральный 18мм',
    category: 'Плитные',
    unit: 'лист',
    currentStock: 32,
    minStockLevel: 50,
    unitCostKZT: 19800,
    totalValueKZT: 633600,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Стеллаж В-3',
    isLowStock: true,
  },
  {
    id: '6',
    sku: 'MAT-CHP-002',
    name: 'ЛДСП Lamarty Белый базовый 16мм',
    category: 'Плитные',
    unit: 'лист',
    currentStock: 110,
    minStockLevel: 60,
    unitCostKZT: 11500,
    totalValueKZT: 1265000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Стеллаж В-4',
  },
  {
    id: '7',
    sku: 'MAT-PLY-001',
    name: 'Фанера березовая ФСФ 15мм сорт 2/4',
    category: 'Плитные',
    unit: 'лист',
    currentStock: 40,
    minStockLevel: 25,
    unitCostKZT: 9800,
    totalValueKZT: 392000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Стеллаж С-1',
  },
  {
    id: '8',
    sku: 'MAT-SCR-001',
    name: 'Конфирматы 7х50мм оцинкованные',
    category: 'Фурнитура',
    unit: 'упак',
    currentStock: 24,
    minStockLevel: 10,
    unitCostKZT: 4500,
    totalValueKZT: 108000,
    supplier: 'ТОО "Blum & Фитинг KZ"',
    location: 'Шкаф F-1',
  },
  {
    id: '9',
    sku: 'MAT-HNG-001',
    name: 'Петля Blum CLIP top BLUMOTION 110° с доводчиком',
    category: 'Фурнитура',
    unit: 'шт',
    currentStock: 340,
    minStockLevel: 150,
    unitCostKZT: 1650,
    totalValueKZT: 561000,
    supplier: 'ТОО "Blum & Фитинг KZ"',
    location: 'Шкаф F-2',
  },
  {
    id: '10',
    sku: 'MAT-HND-001',
    name: 'Ручка мебельная скоба 160мм Черный матовый',
    category: 'Фурнитура',
    unit: 'шт',
    currentStock: 80,
    minStockLevel: 100,
    unitCostKZT: 1200,
    totalValueKZT: 96000,
    supplier: 'ТОО "Blum & Фитинг KZ"',
    location: 'Шкаф F-3',
    isLowStock: true,
  },
  {
    id: '11',
    sku: 'MAT-RAL-001',
    name: 'Направляющие скрытого монтажа Blum Tandem 500мм',
    category: 'Фурнитура',
    unit: 'компл',
    currentStock: 75,
    minStockLevel: 40,
    unitCostKZT: 6900,
    totalValueKZT: 517500,
    supplier: 'ТОО "Blum & Фитинг KZ"',
    location: 'Шкаф F-4',
  },
  {
    id: '12',
    sku: 'MAT-GLU-001',
    name: 'Клей столярный Titebond II Premium Wood Glue (10л)',
    category: 'ЛКМ и клей',
    unit: 'канистра',
    currentStock: 14,
    minStockLevel: 6,
    unitCostKZT: 32000,
    totalValueKZT: 448000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Хим. бокс 2',
  },
  {
    id: '13',
    sku: 'MAT-PNT-001',
    name: 'Эмаль полиуретановая Renner белая шелковисто-матовая',
    category: 'ЛКМ и клей',
    unit: 'кг',
    currentStock: 65,
    minStockLevel: 30,
    unitCostKZT: 7800,
    totalValueKZT: 507000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Малярный склад',
  },
  {
    id: '14',
    sku: 'MAT-VRN-001',
    name: 'Лак полиуретановый Sayerlack полуглянцевый',
    category: 'ЛКМ и клей',
    unit: 'кг',
    currentStock: 35,
    minStockLevel: 20,
    unitCostKZT: 8400,
    totalValueKZT: 294000,
    supplier: 'ТОО "Тимбер Азия"',
    location: 'Малярный склад',
  },
  {
    id: '15',
    sku: 'MAT-FAB-001',
    name: 'Велюр мебельный Teddy Emerald антикоготь',
    category: 'Обивка',
    unit: 'пог. м',
    currentStock: 120,
    minStockLevel: 50,
    unitCostKZT: 4900,
    totalValueKZT: 588000,
    supplier: 'ТОО "SilkWay Textiles"',
    location: 'Текстильный стеллаж',
  },
  {
    id: '16',
    sku: 'MAT-FOM-001',
    name: 'Поролон HR 3535 высокоэластичный (100мм)',
    category: 'Обивка',
    unit: 'лист',
    currentStock: 15,
    minStockLevel: 20,
    unitCostKZT: 13500,
    totalValueKZT: 202500,
    supplier: 'ТОО "SilkWay Textiles"',
    location: 'Текстильный стеллаж',
    isLowStock: true,
  },
];

export default function WarehouseOnePage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Все');
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [materials, setMaterials] = useState(initialMaterials);
  const [successToast, setSuccessToast] = useState('');

  // Form states for quick receipt
  const [selectedMatSku, setSelectedMatSku] = useState(initialMaterials[0].sku);
  const [receiptQty, setReceiptQty] = useState('10');
  const [receiptRef, setReceiptRef] = useState('ТТН-2026/84');

  const categories = ['Все', 'Древесина', 'Плитные', 'Фурнитура', 'ЛКМ и клей', 'Обивка'];

  const filteredMaterials = materials.filter((m) => {
    const matchesCategory = selectedCategory === 'Все' || m.category === selectedCategory;
    const matchesSearch =
      m.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.supplier.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const totalWarehouseValue = materials.reduce((acc, curr) => acc + curr.totalValueKZT, 0);
  const lowStockCount = materials.filter((m) => m.currentStock <= m.minStockLevel).length;

  const handleCreateReceipt = (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseFloat(receiptQty);
    if (!qty || qty <= 0) return;

    setMaterials((prev) =>
      prev.map((m) => {
        if (m.sku === selectedMatSku) {
          const newStock = m.currentStock + qty;
          return {
            ...m,
            currentStock: newStock,
            totalValueKZT: newStock * m.unitCostKZT,
            isLowStock: newStock <= m.minStockLevel,
          };
        }
        return m;
      }),
    );

    setShowReceiptModal(false);
    setSuccessToast(`Приход успешно проведен! Добавлено ${qty} ед. на Склад №1`);
    setTimeout(() => setSuccessToast(''), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {successToast && (
        <div className="fixed top-4 right-4 z-50 bg-emerald-700 text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-2 text-sm font-medium animate-in fade-in slide-in-from-top duration-300">
          <CheckCircle2 className="w-5 h-5 text-emerald-300" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Top Breadcrumb & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-furni-muted mb-1">
            <Link href="/warehouses" className="hover:underline flex items-center gap-1">
              <ChevronLeft className="w-3.5 h-3.5" /> Склады
            </Link>
            <span>/</span>
            <span className="font-medium text-furni-text">Склад №1</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-furni-text">
              Склад №1 — Сырье и материалы
            </h1>
            <Badge variant="warning">WH-1</Badge>
          </div>
          <p className="text-xs text-furni-muted mt-0.5">
            Учет массивной древесины, плитных материалов, мебельной фурнитуры, ЛКМ и наполнителей
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={<ArrowDownLeft className="w-4 h-4" />}
            onClick={() => setShowReceiptModal(true)}
          >
            Оформить приход
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<ArrowUpRight className="w-4 h-4" />}
            onClick={() => {
              alert('Отпуск сырья в производство привязывается к технологической карте (BOM)');
            }}
          >
            Отпуск в цех
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<ClipboardList className="w-4 h-4" />}
            onClick={() => alert('Режим инвентаризации Склада №1')}
          >
            Инвентаризация
          </Button>
        </div>
      </div>

      {/* Warehouse Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-furni-muted">Суммарная оценка остатка</div>
          <div className="text-xl font-bold text-furni-primary mt-1">
            {formatKZT(totalWarehouseValue)}
          </div>
          <div className="text-[11px] text-stone-500 mt-1">По учетным ценам закупки</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-furni-muted">Номенклатурных позиций</div>
          <div className="text-xl font-bold text-furni-text mt-1">{materials.length} SKU</div>
          <div className="text-[11px] text-emerald-600 mt-1">100% подтвержденный аудит</div>
        </Card>

        <Card className="p-4 bg-amber-50/50 border-amber-200">
          <div className="text-xs text-amber-800 font-medium">Критический остаток (дефицит)</div>
          <div className="text-xl font-bold text-amber-700 mt-1">{lowStockCount} позиции</div>
          <div className="text-[11px] text-amber-600 mt-1">Требуется заказ у поставщика</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-furni-muted">Правило списаний</div>
          <div className="text-xs font-semibold text-furni-text mt-1">Защита от минуса</div>
          <div className="text-[11px] text-furni-muted mt-1">Транзакционная блокировка</div>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Category Tabs */}
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

          {/* Search Input */}
          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-stone-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Поиск по названию, SKU, поставщику..."
              className="w-full pl-9 pr-3 py-1.5 bg-furni-bg rounded-lg border border-furni-border text-xs focus:outline-none focus:ring-2 focus:ring-furni-primary/20"
            />
          </div>
        </div>
      </Card>

      {/* Raw Materials Inventory Table */}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#FAFBF9] border-b border-furni-border">
              <tr className="text-furni-muted font-semibold">
                <th className="py-3 px-4">SKU / Артикул</th>
                <th className="py-3 px-4">Наименование материала</th>
                <th className="py-3 px-4">Категория</th>
                <th className="py-3 px-4">Локация</th>
                <th className="py-3 px-4 text-right">Текущий остаток</th>
                <th className="py-3 px-4 text-right">Мин. буфер</th>
                <th className="py-3 px-4 text-right">Цена закупки</th>
                <th className="py-3 px-4 text-right">Стоимость на складе</th>
                <th className="py-3 px-4">Поставщик</th>
                <th className="py-3 px-4 text-center">Статус</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-furni-border-light">
              {filteredMaterials.map((item) => {
                const isLow = item.currentStock <= item.minStockLevel;

                return (
                  <tr
                    key={item.id}
                    className={`hover:bg-stone-50/80 transition-colors ${
                      isLow ? 'bg-amber-50/30' : ''
                    }`}
                  >
                    <td className="py-3 px-4 font-mono font-medium text-stone-600">{item.sku}</td>
                    <td className="py-3 px-4 font-semibold text-furni-text">
                      <div className="flex items-center gap-1.5">
                        {item.name}
                        {isLow && (
                          <span title="Остаток ниже минимального буфера">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-stone-600">{item.category}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-stone-500">
                      {item.location}
                    </td>
                    <td className="py-3 px-4 text-right font-bold font-mono">
                      <span className={isLow ? 'text-rose-600' : 'text-furni-primary'}>
                        {item.currentStock} {item.unit}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-stone-500">
                      {item.minStockLevel} {item.unit}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-stone-700">
                      {formatKZT(item.unitCostKZT)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-furni-text">
                      {formatKZT(item.totalValueKZT)}
                    </td>
                    <td className="py-3 px-4 text-stone-600">{item.supplier}</td>
                    <td className="py-3 px-4 text-center">
                      {isLow ? (
                        <Badge variant="warning">Дефицит</Badge>
                      ) : (
                        <Badge variant="success">В норме</Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal: Quick Stock Receipt */}
      {showReceiptModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-furni-border animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-furni-text">
              Оформить приход материалов (Склад №1)
            </h3>
            <p className="text-xs text-furni-muted mt-1">
              Транзакционная регистрация поступления от поставщика
            </p>

            <form onSubmit={handleCreateReceipt} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Материал (номенклатура)
                </label>
                <select
                  value={selectedMatSku}
                  onChange={(e) => setSelectedMatSku(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs bg-white focus:ring-2 focus:ring-furni-primary"
                >
                  {materials.map((m) => (
                    <option key={m.sku} value={m.sku}>
                      {m.sku} — {m.name} ({m.unit})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Количество к приему
                </label>
                <input
                  type="number"
                  step="any"
                  min="0.1"
                  required
                  value={receiptQty}
                  onChange={(e) => setReceiptQty(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs focus:ring-2 focus:ring-furni-primary"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-furni-text mb-1">
                  Номер накладной / ТТН
                </label>
                <input
                  type="text"
                  required
                  value={receiptRef}
                  onChange={(e) => setReceiptRef(e.target.value)}
                  className="w-full px-3 py-2 border border-furni-border rounded-lg text-xs focus:ring-2 focus:ring-furni-primary"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-furni-border-light">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowReceiptModal(false)}
                >
                  Отмена
                </Button>
                <Button type="submit" variant="primary" size="sm">
                  Подтвердить приход
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
