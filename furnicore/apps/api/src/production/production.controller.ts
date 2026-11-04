import { Controller, Get, Param, Query } from '@nestjs/common';
import { ProductionService } from './production.service';
import { ProductionStatus } from '@prisma/client';

@Controller('production')
export class ProductionController {
  constructor(private productionService: ProductionService) {}

  @Get('orders')
  findAllOrders(@Query('status') status?: ProductionStatus) {
    return this.productionService.findAllOrders(status);
  }

  @Get('recipes')
  findAllRecipes() {
    return this.productionService.findAllRecipes();
  }

  @Get('orders/:id')
  findOrderById(@Param('id') id: string) {
    return this.productionService.findOrderById(id);
  }
}
