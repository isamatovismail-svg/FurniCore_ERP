import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProductCategory } from '@prisma/client';

@Injectable()
export class ProductsService {
  constructor(private prisma: PrismaService) {}

  async findAll(category?: ProductCategory) {
    const wh2 = await this.prisma.warehouse.findUnique({
      where: { code: 'WH-2' },
    });

    const products = await this.prisma.product.findMany({
      where: category ? { category } : undefined,
      include: {
        variants: true,
        recipes: {
          include: {
            items: {
              include: { material: true },
            },
          },
        },
        stockBalances: wh2
          ? {
              where: { warehouseId: wh2.id },
            }
          : true,
      },
      orderBy: { name: 'asc' },
    });

    return products.map((p) => {
      const balance = p.stockBalances[0];
      const currentStock = balance ? Number(balance.currentStock) : 0;
      const reservedStock = balance ? Number(balance.reservedStock) : 0;
      const availableStock = Math.max(0, currentStock - reservedStock);

      const productionCostKZT = Number(p.productionCostKZT);
      const salePriceKZT = Number(p.salePriceKZT);
      const marginKZT = salePriceKZT - productionCostKZT;
      const marginPercent = productionCostKZT > 0 ? (marginKZT / productionCostKZT) * 100 : 0;

      return {
        id: p.id,
        sku: p.sku,
        name: p.name,
        category: p.category,
        description: p.description,
        dimensions: p.dimensions,
        productionCostKZT,
        salePriceKZT,
        marginKZT,
        marginPercent: Math.round(marginPercent * 10) / 10,
        currentStock,
        reservedStock,
        availableStock,
        isActive: p.isActive,
        variantsCount: p.variants.length,
        hasRecipe: p.recipes.length > 0,
        imageUrl: p.imageUrl,
      };
    });
  }

  async findOne(id: string) {
    const product = await this.prisma.product.findUnique({
      where: { id },
      include: {
        variants: true,
        recipes: {
          include: {
            items: {
              include: { material: true },
            },
          },
        },
        stockBalances: {
          include: { warehouse: true },
        },
        stockMovements: {
          orderBy: { createdAt: 'desc' },
          take: 20,
        },
        productionOrders: {
          orderBy: { createdAt: 'desc' },
          take: 10,
        },
      },
    });

    if (!product) throw new NotFoundException('Изделие не найдено');
    return product;
  }
}
