import { Controller, Get, Post, Body, Param, Query, Request } from '@nestjs/common';
import { WarehousesService } from './warehouses.service';
import { MovementType } from '@prisma/client';

@Controller('warehouses')
export class WarehousesController {
  constructor(private warehousesService: WarehousesService) {}

  @Get()
  findAll() {
    return this.warehousesService.findAll();
  }

  @Get('movements')
  getMovements(@Query('warehouseId') warehouseId?: string, @Query('limit') limit?: string) {
    return this.warehousesService.getMovements(warehouseId, limit ? parseInt(limit, 10) : 50);
  }

  @Get(':code')
  findByCode(@Param('code') code: string) {
    return this.warehousesService.findByCode(code.toUpperCase());
  }

  @Post('movements')
  createMovement(
    @Body()
    body: {
      warehouseCode: string;
      type: MovementType;
      materialId?: string;
      productId?: string;
      quantity: number;
      referenceNumber?: string;
      notes?: string;
    },
    @Request() req: any,
  ) {
    return this.warehousesService.createMovement({
      ...body,
      userId: req.user?.id,
    });
  }
}
