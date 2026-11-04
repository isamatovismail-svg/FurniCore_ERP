import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { MovementType, WarehouseType } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

@Injectable()
export class WarehousesService {
  constructor(private prisma: PrismaService) {}

  async findAll() {
    const warehouses = await this.prisma.warehouse.findMany({
      include: {
        stockBalances: {
          include: {
            material: true,
            product: true,
          },
        },
      },
      orderBy: { code: 'asc' },
    });

    return warehouses.map((wh) => {
      let totalStockValueKZT = new Decimal(0);
      let totalItemsCount = 0;

      for (const balance of wh.stockBalances) {
        if (balance.material) {
          totalStockValueKZT = totalStockValueKZT.add(
            balance.currentStock.mul(balance.material.purchaseCostKZT),
          );
          totalItemsCount++;
        } else if (balance.product) {
          totalStockValueKZT = totalStockValueKZT.add(
            balance.currentStock.mul(balance.product.productionCostKZT),
          );
          totalItemsCount++;
        }
      }

      return {
        id: wh.id,
        code: wh.code,
        name: wh.name,
        type: wh.type,
        description: wh.description,
        address: wh.address,
        totalItemsCount,
        totalStockValueKZT: totalStockValueKZT.toNumber(),
      };
    });
  }

  async findByCode(code: string) {
    const warehouse = await this.prisma.warehouse.findUnique({
      where: { code },
      include: {
        stockBalances: {
          include: {
            material: {
              include: { supplier: true },
            },
            product: true,
          },
        },
      },
    });

    if (!warehouse) {
      throw new NotFoundException(`Склад с кодом ${code} не найден`);
    }

    // Recent movements for this warehouse
    const recentMovements = await this.prisma.stockMovement.findMany({
      where: { warehouseId: warehouse.id },
      include: {
        material: true,
        product: true,
        createdBy: {
          select: { fullName: true, role: true },
        },
      },
      orderBy: { createdAt: 'desc' },
      take: 15,
    });

    return {
      ...warehouse,
      recentMovements,
    };
  }

  async getMovements(warehouseId?: string, limit = 50) {
    return this.prisma.stockMovement.findMany({
      where: warehouseId ? { warehouseId } : undefined,
      include: {
        warehouse: true,
        material: true,
        product: true,
        createdBy: {
          select: { fullName: true },
        },
      },
      orderBy: { createdAt: 'desc' },
      take: limit,
    });
  }

  async createMovement(dto: {
    warehouseCode: string;
    type: MovementType;
    materialId?: string;
    productId?: string;
    quantity: number;
    referenceNumber?: string;
    notes?: string;
    userId?: string;
  }) {
    const warehouse = await this.prisma.warehouse.findUnique({
      where: { code: dto.warehouseCode },
    });

    if (!warehouse) {
      throw new NotFoundException(`Склад не найден`);
    }

    if (dto.quantity <= 0) {
      throw new BadRequestException('Количество должно быть больше 0');
    }

    // Execute transaction: verify balance, update stock, prevent negative stock, create movement
    return this.prisma.$transaction(async (tx) => {
      let unitCostKZT = new Decimal(0);
      let unit = 'шт';
      let currentStock = new Decimal(0);
      let balanceRecord: any;

      if (warehouse.type === WarehouseType.RAW_MATERIALS) {
        if (!dto.materialId) {
          throw new BadRequestException('Необходимо указать материал для Склада №1');
        }
        const material = await tx.material.findUnique({
          where: { id: dto.materialId },
        });
        if (!material) throw new NotFoundException('Материал не найден');

        unitCostKZT = material.purchaseCostKZT;
        unit = material.unit;

        balanceRecord = await tx.stockBalance.findUnique({
          where: {
            warehouseId_materialId: {
              warehouseId: warehouse.id,
              materialId: dto.materialId,
            },
          },
        });
      } else {
        if (!dto.productId) {
          throw new BadRequestException('Необходимо указать изделие для Склада №2');
        }
        const product = await tx.product.findUnique({
          where: { id: dto.productId },
        });
        if (!product) throw new NotFoundException('Изделие не найдено');

        unitCostKZT = product.productionCostKZT;
        unit = 'шт';

        balanceRecord = await tx.stockBalance.findUnique({
          where: {
            warehouseId_productId: {
              warehouseId: warehouse.id,
              productId: dto.productId,
            },
          },
        });
      }

      currentStock = balanceRecord ? balanceRecord.currentStock : new Decimal(0);
      const qtyDecimal = new Decimal(dto.quantity);
      let newStock = currentStock;

      if (dto.type === MovementType.RECEIPT) {
        newStock = currentStock.add(qtyDecimal);
      } else if (dto.type === MovementType.ISSUE || dto.type === MovementType.SHIPMENT) {
        if (currentStock.lessThan(qtyDecimal)) {
          throw new BadRequestException(
            `Недостаточно остатка на складе! Текущий остаток: ${currentStock}, запрошено: ${dto.quantity}. Отрицательные остатки запрещены.`,
          );
        }
        newStock = currentStock.sub(qtyDecimal);
      } else if (dto.type === MovementType.ADJUSTMENT) {
        newStock = qtyDecimal;
      }

      // Update or create balance
      if (balanceRecord) {
        await tx.stockBalance.update({
          where: { id: balanceRecord.id },
          data: {
            currentStock: newStock,
            lastCountedAt: new Date(),
          },
        });
      } else {
        await tx.stockBalance.create({
          data: {
            warehouseId: warehouse.id,
            materialId: dto.materialId,
            productId: dto.productId,
            currentStock: newStock,
            lastCountedAt: new Date(),
          },
        });
      }

      const count = await tx.stockMovement.count();
      const movementNumber = `MOV-${new Date().getFullYear()}-${String(count + 1).padStart(5, '0')}`;

      return tx.stockMovement.create({
        data: {
          movementNumber,
          type: dto.type,
          warehouseId: warehouse.id,
          materialId: dto.materialId,
          productId: dto.productId,
          quantity: qtyDecimal,
          unit,
          unitCostKZT,
          totalCostKZT: qtyDecimal.mul(unitCostKZT),
          referenceNumber: dto.referenceNumber,
          notes: dto.notes,
          createdById: dto.userId,
        },
      });
    });
  }
}
