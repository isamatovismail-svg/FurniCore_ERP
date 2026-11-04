import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { MaterialCategory } from '@prisma/client';

@Injectable()
export class MaterialsService {
  constructor(private prisma: PrismaService) {}

  async findAll(category?: MaterialCategory, lowStockOnly?: boolean) {
    const wh1 = await this.prisma.warehouse.findUnique({
      where: { code: 'WH-1' },
    });

    const materials = await this.prisma.material.findMany({
      where: category ? { category } : undefined,
      include: {
        supplier: true,
        stockBalances: wh1
          ? {
              where: { warehouseId: wh1.id },
            }
          : true,
      },
      orderBy: { name: 'asc' },
    });

    const mapped = materials.map((m) => {
      const balance = m.stockBalances[0];
      const currentStock = balance ? Number(balance.currentStock) : 0;
      const minStockLevel = Number(m.minStockLevel);
      const isLowStock = currentStock <= minStockLevel;

      return {
        id: m.id,
        sku: m.sku,
        name: m.name,
        category: m.category,
        unit: m.unit,
        currentStock,
        minStockLevel,
        purchaseCostKZT: Number(m.purchaseCostKZT),
        location: m.location,
        isLowStock,
        supplierName: m.supplier?.name || 'Прямая закупка',
      };
    });

    if (lowStockOnly) {
      return mapped.filter((item) => item.isLowStock);
    }

    return mapped;
  }

  async findOne(id: string) {
    const material = await this.prisma.material.findUnique({
      where: { id },
      include: {
        supplier: true,
        stockBalances: {
          include: { warehouse: true },
        },
        stockMovements: {
          orderBy: { createdAt: 'desc' },
          take: 20,
        },
      },
    });

    if (!material) throw new NotFoundException('Материал не найден');
    return material;
  }
}
