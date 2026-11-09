import { Controller, Get, Param, Query } from '@nestjs/common';
import { MaterialsService } from './materials.service';
import { MaterialCategory } from '@prisma/client';

@Controller('materials')
export class MaterialsController {
  constructor(private materialsService: MaterialsService) {}

  @Get()
  findAll(
    @Query('category') category?: MaterialCategory,
    @Query('lowStock') lowStock?: string,
  ) {
    return this.materialsService.findAll(category, lowStock === 'true');
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.materialsService.findOne(id);
  }
}
