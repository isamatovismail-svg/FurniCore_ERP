import { ProductCategory, MaterialCategory, UserRole, MovementType, ProductionStatus } from '../constants';

export interface UserSummary {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  phone?: string;
  avatarUrl?: string;
  isActive: boolean;
}

export interface WarehouseDto {
  id: string;
  code: string;
  name: string;
  type: 'RAW_MATERIALS' | 'FINISHED_PRODUCTS';
  description?: string;
  address?: string;
  totalItemsCount: number;
  totalStockValueKZT: number;
}

export interface MaterialDto {
  id: string;
  sku: string;
  name: string;
  category: MaterialCategory;
  unit: string;
  currentStock: number;
  minStockLevel: number;
  purchaseCostKZT: number;
  location?: string;
  isLowStock: boolean;
  supplierName?: string;
}

export interface ProductDto {
  id: string;
  sku: string;
  name: string;
  category: ProductCategory;
  description?: string;
  dimensions?: string; // e.g. "2000x1200x600 мм"
  productionCostKZT: number;
  salePriceKZT: number;
  currentStock: number;
  reservedStock: number;
  availableStock: number;
  isActive: boolean;
  imageUrl?: string;
}

export interface StockMovementDto {
  id: string;
  movementNumber: string;
  type: MovementType;
  warehouseId: string;
  warehouseName: string;
  itemId: string;
  itemName: string;
  itemSku: string;
  quantity: number;
  unit: string;
  unitCostKZT: number;
  totalCostKZT: number;
  performedBy: string;
  referenceNumber?: string;
  notes?: string;
  createdAt: string;
}

export interface DashboardMetricsDto {
  totalRevenueKZT: number;
  grossProfitKZT: number;
  netProfitKZT: number;
  totalExpensesKZT: number;
  rawMaterialStockCount: number;
  rawMaterialStockValueKZT: number;
  finishedProductsStockCount: number;
  finishedProductsStockValueKZT: number;
  activeProductionOrdersCount: number;
  pendingCustomerOrdersCount: number;
  lowStockAlertsCount: number;
  revenueVsExpenseChart: Array<{
    month: string;
    revenue: number;
    expenses: number;
    profit: number;
  }>;
  categoryDistribution: Array<{
    name: string;
    value: number;
    count: number;
  }>;
}
