import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { WarehousesModule } from './warehouses/warehouses.module';
import { MaterialsModule } from './materials/materials.module';
import { ProductsModule } from './products/products.module';
import { ProductionModule } from './production/production.module';
import { DashboardModule } from './dashboard/dashboard.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '../../.env',
    }),
    PrismaModule,
    AuthModule,
    WarehousesModule,
    MaterialsModule,
    ProductsModule,
    ProductionModule,
    DashboardModule,
  ],
})
export class AppModule {}
