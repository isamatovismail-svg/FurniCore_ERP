export enum UserRole {
  OWNER = 'OWNER',
  ADMIN = 'ADMIN',
  ACCOUNTANT = 'ACCOUNTANT',
  PRODUCTION_MANAGER = 'PRODUCTION_MANAGER',
  WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER',
  SALES_MANAGER = 'SALES_MANAGER',
  WORKER = 'WORKER',
}

export const ROLE_LABELS_RU: Record<UserRole, string> = {
  [UserRole.OWNER]: 'Владелец',
  [UserRole.ADMIN]: 'Администратор',
  [UserRole.ACCOUNTANT]: 'Бухгалтер',
  [UserRole.PRODUCTION_MANAGER]: 'Начальник производства',
  [UserRole.WAREHOUSE_MANAGER]: 'Заведующий складом',
  [UserRole.SALES_MANAGER]: 'Менеджер по продажам',
  [UserRole.WORKER]: 'Мастер цеха',
};

export enum WarehouseCode {
  WAREHOUSE_1 = 'WH-1', // Raw Materials
  WAREHOUSE_2 = 'WH-2', // Finished Products
}

export const WAREHOUSE_CONFIG = {
  [WarehouseCode.WAREHOUSE_1]: {
    name: 'Склад №1 — Сырье и материалы',
    shortName: 'Склад сырья',
    code: WarehouseCode.WAREHOUSE_1,
    type: 'RAW_MATERIALS',
    description: 'Массив, ЛДСП, МДФ, фурнитура, ЛКМ, клеи, наполнители и ткани',
  },
  [WarehouseCode.WAREHOUSE_2]: {
    name: 'Склад №2 — Готовая продукция',
    shortName: 'Склад готовой продукции',
    code: WarehouseCode.WAREHOUSE_2,
    type: 'FINISHED_PRODUCTS',
    description: 'Готовые шкафы, столы, кровати, кухни, диваны и клиентские резервы',
  },
};

export enum ProductCategory {
  WARDROBE = 'WARDROBE',
  TABLE = 'TABLE',
  BED = 'BED',
  KITCHEN = 'KITCHEN',
  SOFA = 'SOFA',
  OTHER = 'OTHER',
}

export const PRODUCT_CATEGORY_LABELS_RU: Record<ProductCategory, string> = {
  [ProductCategory.WARDROBE]: 'Шкафы',
  [ProductCategory.TABLE]: 'Столы',
  [ProductCategory.BED]: 'Кровати',
  [ProductCategory.KITCHEN]: 'Кухни',
  [ProductCategory.SOFA]: 'Диваны',
  [ProductCategory.OTHER]: 'Прочая мебель',
};

export enum MaterialCategory {
  WOOD = 'WOOD',
  MDF = 'MDF',
  CHIPBOARD = 'CHIPBOARD',
  PLYWOOD = 'PLYWOOD',
  HARDWARE_SCREWS = 'HARDWARE_SCREWS',
  HARDWARE_HINGES = 'HARDWARE_HINGES',
  HARDWARE_HANDLES = 'HARDWARE_HANDLES',
  HARDWARE_RAILS = 'HARDWARE_RAILS',
  GLUE = 'GLUE',
  PAINT = 'PAINT',
  VARNISH = 'VARNISH',
  FABRIC = 'FABRIC',
  FOAM = 'FOAM',
  OTHER = 'OTHER',
}

export const MATERIAL_CATEGORY_LABELS_RU: Record<MaterialCategory, string> = {
  [MaterialCategory.WOOD]: 'Массив дерева',
  [MaterialCategory.MDF]: 'МДФ панели',
  [MaterialCategory.CHIPBOARD]: 'ЛДСП',
  [MaterialCategory.PLYWOOD]: 'Фанера',
  [MaterialCategory.HARDWARE_SCREWS]: 'Крепеж и саморезы',
  [MaterialCategory.HARDWARE_HINGES]: 'Петли мебельные',
  [MaterialCategory.HARDWARE_HANDLES]: 'Ручки мебельные',
  [MaterialCategory.HARDWARE_RAILS]: 'Направляющие ящиков',
  [MaterialCategory.GLUE]: 'Клей столярный',
  [MaterialCategory.PAINT]: 'Краска',
  [MaterialCategory.VARNISH]: 'Лак мебельный',
  [MaterialCategory.FABRIC]: 'Обивочная ткань',
  [MaterialCategory.FOAM]: 'Поролон (ППУ)',
  [MaterialCategory.OTHER]: 'Прочие материалы',
};

export enum MovementType {
  RECEIPT = 'RECEIPT',         // Поступление
  ISSUE = 'ISSUE',             // Списание / Отпуск в производство
  TRANSFER = 'TRANSFER',       // Перемещение
  ADJUSTMENT = 'ADJUSTMENT',   // Инвентаризация / Корректировка
  RESERVATION = 'RESERVATION', // Резервирование
  SHIPMENT = 'SHIPMENT',       // Отгрузка клиенту
}

export const MOVEMENT_TYPE_LABELS_RU: Record<MovementType, string> = {
  [MovementType.RECEIPT]: 'Поступление',
  [MovementType.ISSUE]: 'Отпуск в цех',
  [MovementType.TRANSFER]: 'Перемещение',
  [MovementType.ADJUSTMENT]: 'Инвентаризация',
  [MovementType.RESERVATION]: 'Резерв заказа',
  [MovementType.SHIPMENT]: 'Отгрузка клиенту',
};

export enum ProductionStatus {
  DRAFT = 'DRAFT',
  PLANNED = 'PLANNED',
  IN_PROGRESS = 'IN_PROGRESS',
  QUALITY_CHECK = 'QUALITY_CHECK',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
}

export const PRODUCTION_STATUS_LABELS_RU: Record<ProductionStatus, string> = {
  [ProductionStatus.DRAFT]: 'Черновик',
  [ProductionStatus.PLANNED]: 'Запланирован',
  [ProductionStatus.IN_PROGRESS]: 'В производстве',
  [ProductionStatus.QUALITY_CHECK]: 'Контроль качества (ОТК)',
  [ProductionStatus.COMPLETED]: 'Выпущен на склад',
  [ProductionStatus.CANCELLED]: 'Отменен',
};
