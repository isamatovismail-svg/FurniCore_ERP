'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  Layers,
  Search,
  Filter,
  AlertTriangle,
  ArrowDownLeft,
  ChevronLeft,
  CheckCircle2,
  Boxes,
  Plus,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT } from '@/lib/utils';

const allMaterials = [
  { sku: 'MAT-WOD-001', name: 'Массив дуба 50мм (сухой калиброванный)', category: 'Древесина', unit: 'м³', currentStock: 12.5, minStockLevel: 5.0, unitCostKZT: 380000, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Секция А-1' },
  { sku: 'MAT-WOD-002', name: 'Массив сосны 40мм обрезной', category: 'Древесина', unit: 'м³', currentStock: 18.0, minStockLevel: 8.0, unitCostKZT: 145000, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Секция А-2' },
  { sku: 'MAT-MDF-001', name: 'МДФ влагостойкий 16мм Kronospan 2800x2070', category: 'Плитные', unit: 'лист', currentStock: 85, minStockLevel: 40, unitCostKZT: 14200, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Стеллаж В-1' },
  { sku: 'MAT-MDF-002', name: 'МДФ шлифованный 18мм Kastamonu 2800x2070', category: 'Плитные', unit: 'лист', currentStock: 45, minStockLevel: 30, unitCostKZT: 16500, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Стеллаж В-2' },
  { sku: 'MAT-CHP-001', name: 'ЛДСП Egger Дуб Галифакс натуральный 18мм', category: 'Плитные', unit: 'лист', currentStock: 32, minStockLevel: 50, unitCostKZT: 19800, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Стеллаж В-3', isLow: true },
  { sku: 'MAT-CHP-002', name: 'ЛДСП Lamarty Белый базовый 16мм', category: 'Плитные', unit: 'лист', currentStock: 110, minStockLevel: 60, unitCostKZT: 11500, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Стеллаж В-4' },
  { sku: 'MAT-PLY-001', name: 'Фанера березовая ФСФ 15мм сорт 2/4', category: 'Плитные', unit: 'лист', currentStock: 40, minStockLevel: 25, unitCostKZT: 9800, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Стеллаж С-1' },
  { sku: 'MAT-SCR-001', name: 'Конфирматы 7х50мм оцинкованные', category: 'Фурнитура', unit: 'упак', currentStock: 24, minStockLevel: 10, unitCostKZT: 4500, supplier: 'ТОО "Blum & Фитинг KZ"', location: 'WH-1 / Шкаф F-1' },
  { sku: 'MAT-HNG-001', name: 'Петля Blum CLIP top BLUMOTION 110° с доводчиком', category: 'Фурнитура', unit: 'шт', currentStock: 340, minStockLevel: 150, unitCostKZT: 1650, supplier: 'ТОО "Blum & Фитинг KZ"', location: 'WH-1 / Шкаф F-2' },
  { sku: 'MAT-HND-001', name: 'Ручка мебельная скоба 160мм Черный матовый', category: 'Фурнитура', unit: 'шт', currentStock: 80, minStockLevel: 100, unitCostKZT: 1200, supplier: 'ТОО "Blum & Фитинг KZ"', location: 'WH-1 / Шкаф F-3', isLow: true },
  { sku: 'MAT-RAL-001', name: 'Направляющие скрытого монтажа Blum Tandem 500мм', category: 'Фурнитура', unit: 'компл', currentStock: 75, minStockLevel: 40, unitCostKZT: 6900, supplier: 'ТОО "Blum & Фитинг KZ"', location: 'WH-1 / Шкаф F-4' },
  { sku: 'MAT-GLU-001', name: 'Клей столярный Titebond II Premium Wood Glue', category: 'ЛКМ и клей', unit: 'канистра', currentStock: 14, minStockLevel: 6, unitCostKZT: 32000, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Хим. бокс 2' },
  { sku: 'MAT-PNT-001', name: 'Эмаль полиуретановая Renner шелковисто-матовая', category: 'ЛКМ и клей', unit: 'кг', currentStock: 65, minStockLevel: 30, unitCostKZT: 7800, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Малярный склад' },
  { sku: 'MAT-VRN-001', name: 'Лак полиуретановый Sayerlack полуглянцевый', category: 'ЛКМ и клей', unit: 'кг', currentStock: 35, minStockLevel: 20, unitCostKZT: 8400, supplier: 'ТОО "Тимбер Азия"', location: 'WH-1 / Малярный склад' },
  { sku: 'MAT-FAB-001', name: 'Велюр мебельный Teddy Emerald антикоготь', category: 'Обивка', unit: 'пог. м', currentStock: 120, minStockLevel: 50, unitCostKZT: 4900, supplier: 'ТОО "SilkWay Textiles"', location: 'WH-1 / Текстильный стеллаж' },
  { sku: 'MAT-FOM-001', name: 'Пенополиуретан высокоэластичный HR 3535 (100мм)', category: 'Обивка', unit: 'лист', currentStock: 15, minStockLevel: 20, unitCostKZT: 13500, supplier: 'ТОО "SilkWay Textiles"', location: 'WH-1 / Текстильный стеллаж', isLow: true },
];

export default function MaterialsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Все');
  const [onlyLowStock, setOnlyLowStock] = useState(false);

  const categories = ['Все', 'Древесина', 'Плитные', 'Фурнитура', 'ЛКМ и клей', 'Обивка'];

  const filtered = allMaterials.filter((m) => {
    const matchesCat = selectedCategory === 'Все' || m.category === selectedCategory;
    const matchesSearch =
      m.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.supplier.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesLow = onlyLowStock ? m.currentStock <= m.minStockLevel : true;
    return matchesCat && matchesSearch && matchesLow;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-furni-text">
            Материалы и сырье
          </h1>
          <p className="text-sm text-furni-muted mt-0.5">
            Справочник сырья, нормы минимального складского буфера и мониторинг дефицита
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/warehouses/wh-1">
            <Button variant="primary" size="sm" icon={<ArrowDownLeft className="w-4 h-4" />}>
              Перейти к операциям WH-1
            </Button>
          </Link>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => setSelectedCategory(c)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  selectedCategory === c
                    ? 'bg-furni-primary text-white font-semibold'
                    : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
                }`}
              >
                {c}
              </button>
            ))}

            <button
              onClick={() => setOnlyLowStock(!onlyLowStock)}
              className={`ml-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                onlyLowStock
                  ? 'bg-amber-600 text-white font-semibold'
                  : 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Только дефицит (3)</span>
            </button>
          </div>

          <div className="relative min-w-[280px]">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-stone-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Поиск по артикулу, названию..."
              className="w-full pl-9 pr-3 py-1.5 bg-furni-bg rounded-lg border border-furni-border text-xs focus:outline-none focus:ring-2 focus:ring-furni-primary/20"
            />
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#FAFBF9] border-b border-furni-border">
              <tr className="text-furni-muted font-semibold">
                <th className="py-3 px-4">Артикул</th>
                <th className="py-3 px-4">Материал</th>
                <th className="py-3 px-4">Категория</th>
                <th className="py-3 px-4">Складское размещение</th>
                <th className="py-3 px-4 text-right">Остаток</th>
                <th className="py-3 px-4 text-right">Мин. буфер</th>
                <th className="py-3 px-4 text-right">Цена закупки</th>
                <th className="py-3 px-4">Поставщик</th>
                <th className="py-3 px-4 text-center">Статус</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-furni-border-light">
              {filtered.map((m) => {
                const isLow = m.currentStock <= m.minStockLevel;
                return (
                  <tr key={m.sku} className={`hover:bg-stone-50/80 ${isLow ? 'bg-amber-50/30' : ''}`}>
                    <td className="py-3 px-4 font-mono font-medium text-stone-600">{m.sku}</td>
                    <td className="py-3 px-4 font-semibold text-furni-text">{m.name}</td>
                    <td className="py-3 px-4 text-stone-600">{m.category}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-stone-500">{m.location}</td>
                    <td className="py-3 px-4 text-right font-bold font-mono">
                      <span className={isLow ? 'text-rose-600' : 'text-furni-primary'}>
                        {m.currentStock} {m.unit}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-stone-500">
                      {m.minStockLevel} {m.unit}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-semibold text-stone-800">
                      {formatKZT(m.unitCostKZT)}
                    </td>
                    <td className="py-3 px-4 text-stone-600">{m.supplier}</td>
                    <td className="py-3 px-4 text-center">
                      {isLow ? (
                        <Badge variant="warning">Требуется заказ</Badge>
                      ) : (
                        <Badge variant="success">В наличии</Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
