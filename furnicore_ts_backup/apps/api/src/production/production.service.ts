import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProductionStatus } from '@prisma/client';

@Injectable()
export class ProductionService {
  constructor(private prisma: PrismaService) {}

  async findAllOrders(status?: ProductionStatus) {
    return this.prisma.productionOrder.findMany({
      where: status ? { status } : undefined,
      include: {
        product: true,
        recipe: {
          include: {
            items: {
              include: { material: true },
            },
          },
        },
        supervisor: {
          select: { id: true, fullName: true, role: true },
        },
      },
      orderBy: { plannedStartDate: 'desc' },
    });
  }

  async findAllRecipes() {
    return this.prisma.recipe.findMany({
      include: {
        product: true,
        items: {
          include: {
            material: true,
          },
        },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOrderById(id: string) {
    const order = await this.prisma.productionOrder.findUnique({
      where: { id },
      include: {
        product: true,
        recipe: {
          include: {
            items: {
              include: { material: true },
            },
          },
        },
        supervisor: true,
      },
    });

    if (!order) throw new NotFoundException('Производственный заказ не найден');
    return order;
  }
}
