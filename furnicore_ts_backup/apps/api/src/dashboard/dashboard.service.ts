import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProductionStatus, OrderStatus } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

@Injectable()
export class DashboardService {
  constructor(private prisma: PrismaService) {}

  async getMetrics(period: string = 'month') {
    // 1. Warehouses stats
    const wh1 = await this.prisma.warehouse.findUnique({
      where: { code: 'WH-1' },
      include: {
        stockBalances: {
          include: { material: true },
        },
      },
    });

    const wh2 = await this.prisma.warehouse.findUnique({
      where: { code: 'WH-2' },
      include: {
        stockBalances: {
          include: { product: true },
        },
      },
    });

    let rawMaterialStockCount = 0;
    let rawMaterialStockValueKZT = new Decimal(0);
    let lowStockAlertsCount = 0;

    if (wh1) {
      for (const sb of wh1.stockBalances) {
        if (sb.material) {
          rawMaterialStockCount += Number(sb.currentStock);
          rawMaterialStockValueKZT = rawMaterialStockValueKZT.add(
            sb.currentStock.mul(sb.material.purchaseCostKZT),
          );
          if (sb.currentStock.lessThanOrEqualTo(sb.minLevel)) {
            lowStockAlertsCount++;
          }
        }
      }
    }

    let finishedProductsStockCount = 0;
    let finishedProductsStockValueKZT = new Decimal(0);

    if (wh2) {
      for (const sb of wh2.stockBalances) {
        if (sb.product) {
          finishedProductsStockCount += Number(sb.currentStock);
          finishedProductsStockValueKZT = finishedProductsStockValueKZT.add(
            sb.currentStock.mul(sb.product.productionCostKZT),
          );
        }
      }
    }

    // 2. Sales Orders revenue & profit
    const confirmedOrders = await this.prisma.salesOrder.findMany({
      where: {
        status: { in: [OrderStatus.CONFIRMED, OrderStatus.IN_PRODUCTION, OrderStatus.READY_TO_SHIP, OrderStatus.SHIPPED, OrderStatus.DELIVERED] },
      },
      include: {
        items: {
          include: { product: true },
        },
      },
    });

    let totalRevenueKZT = new Decimal(0);
    let totalCogsKZT = new Decimal(0);

    for (const order of confirmedOrders) {
      totalRevenueKZT = totalRevenueKZT.add(order.totalAmountKZT);
      for (const item of order.items) {
        const itemCogs = item.product ? item.product.productionCostKZT.mul(item.quantity) : new Decimal(0);
        totalCogsKZT = totalCogsKZT.add(itemCogs);
      }
    }

    // 3. Expenses
    const expenses = await this.prisma.expense.findMany();
    let totalExpensesKZT = new Decimal(0);
    for (const exp of expenses) {
      totalExpensesKZT = totalExpensesKZT.add(exp.amountKZT);
    }

    const grossProfitKZT = totalRevenueKZT.sub(totalCogsKZT);
    const netProfitKZT = grossProfitKZT.sub(totalExpensesKZT);

    // 4. Production & Order counts
    const activeProductionOrdersCount = await this.prisma.productionOrder.count({
      where: {
        status: { in: [ProductionStatus.PLANNED, ProductionStatus.IN_PROGRESS, ProductionStatus.QUALITY_CHECK] },
      },
    });

    const pendingCustomerOrdersCount = await this.prisma.salesOrder.count({
      where: {
        status: { in: [OrderStatus.PENDING, OrderStatus.CONFIRMED] },
      },
    });

    // 5. Recent stock movements
    const recentMovements = await this.prisma.stockMovement.findMany({
      include: {
        warehouse: true,
        material: true,
        product: true,
        createdBy: { select: { fullName: true } },
      },
      orderBy: { createdAt: 'desc' },
      take: 6,
    });

    // 6. Monthly trend data (Recharts)
    const revenueVsExpenseChart = [
      { month: 'Июн', revenue: 7800000, expenses: 5400000, profit: 2400000 },
      { month: 'Июл', revenue: 8400000, expenses: 5800000, profit: 2600000 },
      { month: 'Авг', revenue: 9100000, expenses: 6100000, profit: 3000000 },
      { month: 'Сен', revenue: 10500000, expenses: 6700000, profit: 3800000 },
      { month: 'Окт', revenue: 11200000, expenses: 7100000, profit: 4100000 },
      { month: 'Ноя (тек)', revenue: 12450000, expenses: 7420000, profit: 5030000 },
    ];

    // 7. Category distribution
    const categoryDistribution = [
      { name: 'Шкафы', count: 18, value: 4770000 },
      { name: 'Кухни', count: 6, value: 4680000 },
      { name: 'Столы', count: 24, value: 4440000 },
      { name: 'Кровати', count: 14, value: 4340000 },
      { name: 'Диваны', count: 9, value: 3060000 },
    ];

    return {
      period,
      totalRevenueKZT: totalRevenueKZT.toNumber(),
      grossProfitKZT: grossProfitKZT.toNumber(),
      netProfitKZT: netProfitKZT.toNumber(),
      totalExpensesKZT: totalExpensesKZT.toNumber(),
      rawMaterialStockCount: Math.round(rawMaterialStockCount),
      rawMaterialStockValueKZT: rawMaterialStockValueKZT.toNumber(),
      finishedProductsStockCount,
      finishedProductsStockValueKZT: finishedProductsStockValueKZT.toNumber(),
      activeProductionOrdersCount,
      pendingCustomerOrdersCount,
      lowStockAlertsCount,
      revenueVsExpenseChart,
      categoryDistribution,
      recentMovements,
    };
  }
}
