'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Armchair,
  Search,
  Filter,
  Plus,
  Layers,
  Sparkles,
  TrendingUp,
  Tag,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Maximize2,
  Settings2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT } from '@/lib/utils';

const initialProducts = [
  {
    id: '1',
    sku: 'PRD-WRD-001',
    name: 'Шкаф 3-дверный "Nordic Loft" с зеркалом',
    category: 'Шкафы',
    dimensions: '2200x1500x600 мм',
    description: 'Корпус ЛДСП Egger Дуб Галифакс, фасады МДФ белый матовый, петли Blum с доводчиком, встроенное зеркало.',
    productionCostKZT: 145000,
    salePriceKZT: 265000,
    currentStock: 6,
    reservedStock: 2,
    availableStock: 4,
    variants: [
      { name: 'Стандарт (Дуб Галифакс/Белый)', extraKZT: 0 },
      { name: 'Премиум (Графит софт-тач)', extraKZT: 25000 },
      { name: 'С подсветкой полок LED', extraKZT: 18000 },
    ],
    recipe: 'Техкарта #WRD-12 (5 материалов)',
    status: 'ACTIVE',
  },
  {
    id: '2',
    sku: 'PRD-TBL-001',
    name: 'Стол обеденный "Almaty Oak" раскладной',
    category: 'Столы',
    dimensions: '1600(2100)x900x760 мм',
    description: 'Столешница из сращенного массива дуба 40мм под матовым лаком Renner, надежное стальное подстолье.',
    productionCostKZT: 98000,
    salePriceKZT: 185000,
    currentStock: 12,
    reservedStock: 3,
    availableStock: 9,
    variants: [
      { name: 'Натуральный дуб', extraKZT: 0 },
      { name: 'Мореный дуб (темный)', extraKZT: 12000 },
    ],
    recipe: 'Техкарта #TBL-04 (3 материала)',
    status: 'ACTIVE',
  },
  {
    id: '3',
    sku: 'PRD-BED-001',
    name: 'Кровать двуспальная "Comfort Prime 180"',
    category: 'Кровати',
    dimensions: '2150x1920x1100 мм (спальное место 180x200)',
    description: 'Мягкое изголовье из антивандального велюра Teddy Emerald, ортопедическое основание и газлифт.',
    productionCostKZT: 165000,
    salePriceKZT: 310000,
    currentStock: 4,
    reservedStock: 1,
    availableStock: 3,
    variants: [
      { name: 'Спальное 180х200см', extraKZT: 0 },
      { name: 'Спальное 200х200см (King size)', extraKZT: 35000 },
    ],
    recipe: 'Техкарта #BED-08 (6 материалов)',
    status: 'ACTIVE',
  },
  {
    id: '4',
    sku: 'PRD-KTC-001',
    name: 'Кухонный гарнитур модульный "Astana Mod" 3.2м',
    category: 'Кухни',
    dimensions: '3200x1800x2300 мм',
    description: 'Фасады МДФ эмаль soft-touch, фурнитура скрытого монтажа Blum Tandembox, влагостойкая столешница 38мм.',
    productionCostKZT: 420000,
    salePriceKZT: 780000,
    currentStock: 2,
    reservedStock: 1,
    availableStock: 1,
    variants: [
      { name: 'Угловая компоновка левая', extraKZT: 0 },
      { name: 'Угловая компоновка правая', extraKZT: 0 },
      { name: 'С островом 1200х800', extraKZT: 140000 },
    ],
    recipe: 'Техкарта #KTC-21 (14 материалов)',
    status: 'ACTIVE',
  },
  {
    id: '5',
    sku: 'PRD-SOF-001',
    name: 'Диван 3-местный прямой "Nomad Lounge"',
    category: 'Диваны',
    dimensions: '2350x1050x880 мм',
    description: 'Каркас из березовой фанеры 15мм и соснового бруса, наполнитель HR3535 + независимый пружинный блок.',
    productionCostKZT: 175000,
    salePriceKZT: 340000,
    currentStock: 5,
    reservedStock: 0,
    availableStock: 5,
    variants: [
      { name: 'Велюр Teddy Изумруд', extraKZT: 0 },
      { name: 'Велюр Teddy Серый графит', extraKZT: 0 },
      { name: 'Букле молочный', extraKZT: 28000 },
    ],
    recipe: 'Техкарта #SOF-02 (7 материалов)',
    status: 'ACTIVE',
  },
];

export default function ProductsPage() {
  const [products, setProducts] = useState(initialProducts);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Все');
  const [selectedProduct, setSelectedProduct] = useState<any>(null);

  const categories = ['Все', 'Шкафы', 'Столы', 'Кровати', 'Кухни', 'Диваны'];

  const filteredProducts = products.filter((p) => {
    const matchesCategory = selectedCategory === 'Все' || p.category === selectedCategory;
    const matchesSearch =
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-furni-text">
            Каталог серийных изделий
          </h1>
          <p className="text-sm text-furni-muted mt-0.5">
            Шкафы, столы, кровати, кухни, диваны — рецептуры, калькуляция себестоимости и складские остатки
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/production">
            <Button variant="outline" size="sm" icon={<Layers className="w-4 h-4" />}>
              Технологические карты (BOM)
            </Button>
          </Link>
          <Button
            variant="primary"
            size="sm"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => alert('Создание нового изделия в каталоге FurniCore')}
          >
            Новое изделие
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
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

          <div className="relative min-w-[280px]">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-stone-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Поиск по названию модели, SKU..."
              className="w-full pl-9 pr-3 py-1.5 bg-furni-bg rounded-lg border border-furni-border text-xs focus:outline-none focus:ring-2 focus:ring-furni-primary/20"
            />
          </div>
        </div>
      </Card>

      {/* Product Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredProducts.map((p) => {
          const marginKZT = p.salePriceKZT - p.productionCostKZT;
          const marginPercent = Math.round((marginKZT / p.productionCostKZT) * 100);

          return (
            <Card
              key={p.id}
              className="flex flex-col justify-between hover:shadow-card-hover transition-all border border-furni-border bg-white"
            >
              <div>
                <div className="flex items-start justify-between">
                  <span className="font-mono text-xs font-semibold text-furni-secondary bg-stone-100 px-2 py-0.5 rounded">
                    {p.sku}
                  </span>
                  <Badge variant="success">В каталоге</Badge>
                </div>

                <h3 className="font-bold text-base text-furni-text mt-3 tracking-tight">
                  {p.name}
                </h3>
                <div className="text-xs text-furni-muted mt-1 font-mono">
                  Габариты: {p.dimensions}
                </div>

                <p className="text-xs text-stone-600 mt-2.5 line-clamp-2 leading-relaxed">
                  {p.description}
                </p>

                {/* Recipe tag */}
                <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-furni-secondary bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                  <Layers className="w-3.5 h-3.5" />
                  <span>{p.recipe}</span>
                </div>

                {/* Financial comparison */}
                <div className="mt-4 pt-3 border-t border-furni-border-light grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-stone-400">Себестоимость:</span>
                    <div className="font-mono font-semibold text-stone-800">
                      {formatKZT(p.productionCostKZT)}
                    </div>
                  </div>
                  <div>
                    <span className="text-stone-400">Цена продажи:</span>
                    <div className="font-mono font-bold text-furni-primary">
                      {formatKZT(p.salePriceKZT)}
                    </div>
                  </div>
                </div>

                {/* Margin pill */}
                <div className="mt-2 text-xs font-mono text-emerald-700 bg-emerald-50/80 px-2 py-1 rounded flex items-center justify-between">
                  <span>Маржинальность:</span>
                  <span className="font-bold">+{marginPercent}% (+{formatKZT(marginKZT)})</span>
                </div>
              </div>

              {/* Bottom stock & actions */}
              <div className="mt-5 pt-3 border-t border-furni-border flex items-center justify-between">
                <div className="text-xs">
                  <span className="text-stone-400">Склад №2: </span>
                  <span className="font-bold text-furni-text">{p.currentStock} шт</span>
                  <span className="text-stone-400"> (резерв: {p.reservedStock})</span>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs py-1"
                  onClick={() => setSelectedProduct(p)}
                >
                  Модификации
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Product Details / Variants Modal */}
      {selectedProduct && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 border border-furni-border animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-xs text-furni-muted">{selectedProduct.sku}</span>
                <h3 className="text-lg font-bold text-furni-text mt-0.5">
                  {selectedProduct.name}
                </h3>
              </div>
              <Badge variant="success">{selectedProduct.category}</Badge>
            </div>

            <div className="mt-4 space-y-3">
              <div className="text-xs text-stone-600 bg-stone-50 p-3 rounded-lg border border-stone-200">
                <span className="font-semibold text-furni-text">Техническое описание: </span>
                {selectedProduct.description}
              </div>

              <div>
                <h4 className="text-xs font-bold text-furni-muted uppercase tracking-wider mb-2">
                  Доступные модификации и комплектации:
                </h4>
                <div className="space-y-1.5">
                  {selectedProduct.variants.map((v: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-2.5 bg-furni-bg rounded-lg border border-furni-border-light flex items-center justify-between text-xs"
                    >
                      <span className="font-medium text-furni-text">{v.name}</span>
                      <span className="font-mono font-semibold text-furni-primary">
                        {v.extraKZT > 0 ? `+${formatKZT(v.extraKZT)}` : 'Базовая'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2 text-xs text-furni-muted flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Историческая себестоимость сохраняется в неизменном виде.</span>
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-furni-border-light flex justify-end">
              <Button variant="primary" size="sm" onClick={() => setSelectedProduct(null)}>
                Закрыть
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
