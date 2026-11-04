'use client';

import React from 'react';
import Link from 'next/link';
import {
  Boxes,
  PackageCheck,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  History,
  PlusCircle,
  ArrowDownLeft,
  ArrowUpRight,
  ShieldCheck,
} from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatKZT } from '@/lib/utils';

export default function WarehousesOverviewPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-furni-text">
              Складской комплекс FurniCore
            </h1>
            <Badge variant="default" className="text-xs">
              Ровно 2 склада
            </Badge>
          </div>
          <p className="text-sm text-furni-muted mt-0.5">
            Строгая двухскладская топология: Склад №1 (Сырье) и Склад №2 (Готовая продукция)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/warehouses/wh-1">
            <Button variant="secondary" size="sm" icon={<ArrowDownLeft className="w-4 h-4" />}>
              Приход на Склад №1
            </Button>
          </Link>
          <Link href="/warehouses/wh-2">
            <Button variant="primary" size="sm" icon={<ArrowUpRight className="w-4 h-4" />}>
              Отгрузка со Склада №2
            </Button>
          </Link>
        </div>
      </div>

      {/* Warehouse Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Warehouse 1: Raw Materials */}
        <Card className="flex flex-col justify-between border-t-4 border-t-amber-600 hover:shadow-card-hover transition-all">
          <div>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-800 flex items-center justify-center font-bold">
                  <Boxes className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-furni-text">Склад №1 — Сырье и материалы</h2>
                    <Badge variant="warning">WH-1</Badge>
                  </div>
                  <p className="text-xs text-furni-muted mt-0.5">
                    г. Алматы, Илийский тракт, 14, Ангар А
                  </p>
                </div>
              </div>
            </div>

            <p className="text-xs text-stone-600 mt-4 bg-stone-50 p-3 rounded-lg border border-stone-200">
              Хранение древесины (массив дуба, сосны), МДФ, ЛДСП, березовой фанеры, фурнитуры
              (петли Blum, направляющие Tandem, ручки), клеев Titebond, эмалей и мебельного велюра.
            </p>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3 mt-4 text-center">
              <div className="p-3 bg-furni-bg rounded-lg">
                <span className="text-[11px] text-furni-muted">Оценка сырья</span>
                <div className="text-base font-bold text-amber-900 mt-1">14 250 000 ₸</div>
              </div>
              <div className="p-3 bg-furni-bg rounded-lg">
                <span className="text-[11px] text-furni-muted">Активных SKU</span>
                <div className="text-base font-bold text-stone-900 mt-1">16 позиций</div>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <span className="text-[11px] text-amber-800 font-semibold">Дефицит запаса</span>
                <div className="text-base font-bold text-amber-700 mt-1">3 позиции</div>
              </div>
            </div>

            {/* Included Categories checklist */}
            <div className="mt-5 space-y-1.5">
              <span className="text-xs font-semibold text-furni-muted uppercase tracking-wider">
                Категории сырья:
              </span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[
                  'Массив дуба/сосны',
                  'МДФ 16-18мм',
                  'ЛДСП Egger',
                  'Фанера березовая',
                  'Петли Blum',
                  'Направляющие',
                  'Клей Titebond',
                  'Эмаль Renner',
                  'Велюр Teddy',
                  'Поролон HR',
                ].map((tag) => (
                  <span
                    key={tag}
                    className="text-[11px] bg-stone-100 text-stone-700 px-2 py-0.5 rounded border border-stone-200"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-furni-border flex items-center justify-between">
            <span className="text-xs text-furni-muted flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Защита от отрицательных остатков
            </span>
            <Link href="/warehouses/wh-1">
              <Button variant="secondary" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>
                Управление Складом №1
              </Button>
            </Link>
          </div>
        </Card>

        {/* Warehouse 2: Finished Products */}
        <Card className="flex flex-col justify-between border-t-4 border-t-emerald-600 hover:shadow-card-hover transition-all">
          <div>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-800 flex items-center justify-center font-bold">
                  <PackageCheck className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-furni-text">
                      Склад №2 — Готовая продукция
                    </h2>
                    <Badge variant="success">WH-2</Badge>
                  </div>
                  <p className="text-xs text-furni-muted mt-0.5">
                    г. Алматы, Илийский тракт, 14, Секция В
                  </p>
                </div>
              </div>
            </div>

            <p className="text-xs text-stone-600 mt-4 bg-stone-50 p-3 rounded-lg border border-stone-200">
              Приемка изделий из производственного цеха после прохождения ОТК: шкафы, обеденные
              столы, двуспальные кровати, кухонные гарнитуры, прямые диваны. Зона резервирования и
              отгрузки клиентам.
            </p>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3 mt-4 text-center">
              <div className="p-3 bg-furni-bg rounded-lg">
                <span className="text-[11px] text-furni-muted">Оценка на складе</span>
                <div className="text-base font-bold text-emerald-800 mt-1">8 450 000 ₸</div>
              </div>
              <div className="p-3 bg-furni-bg rounded-lg">
                <span className="text-[11px] text-furni-muted">Готовых изделий</span>
                <div className="text-base font-bold text-stone-900 mt-1">29 шт</div>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg">
                <span className="text-[11px] text-blue-800 font-semibold">Клиентский резерв</span>
                <div className="text-base font-bold text-blue-700 mt-1">7 шт</div>
              </div>
            </div>

            {/* Products included */}
            <div className="mt-5 space-y-1.5">
              <span className="text-xs font-semibold text-furni-muted uppercase tracking-wider">
                Категории мебели:
              </span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[
                  'Шкафы распашные и купе',
                  'Столы из массива дуба',
                  'Кровати с подъемным механизмом',
                  'Кухонные гарнитуры модульные',
                  'Диваны велюровые',
                ].map((tag) => (
                  <span
                    key={tag}
                    className="text-[11px] bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-furni-border flex items-center justify-between">
            <span className="text-xs text-furni-muted flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Идемпотентность списаний
            </span>
            <Link href="/warehouses/wh-2">
              <Button variant="primary" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>
                Управление Складом №2
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      {/* Principles Banner */}
      <Card className="bg-[#FAFBF9] border-furni-border">
        <h3 className="text-sm font-bold text-furni-text">
          Архитектурное правило FurniCore: Разделение цеха и складов
        </h3>
        <p className="text-xs text-furni-muted mt-1 leading-relaxed">
          Производство — это технологический процесс, а не третий склад. Материалы списываются со
          Склада №1 при передаче в цех. Готовая мебель ставится на баланс Склада №2 только после
          завершения всех операций и штампа ОТК.
        </p>
      </Card>
    </div>
  );
}
