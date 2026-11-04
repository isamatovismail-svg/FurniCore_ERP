import { PrismaClient, Role, WarehouseType, ProductCategory, MaterialCategory, MovementType, ProductionStatus, OrderStatus, ExpenseCategory } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Starting FurniCore ERP database seeding [DEMO DATA]...');

  // Clean existing tables in reverse relation order
  await prisma.auditLog.deleteMany();
  await prisma.expense.deleteMany();
  await prisma.salesOrderItem.deleteMany();
  await prisma.salesOrder.deleteMany();
  await prisma.customer.deleteMany();
  await prisma.stockMovement.deleteMany();
  await prisma.stockBalance.deleteMany();
  await prisma.productionOrder.deleteMany();
  await prisma.recipeItem.deleteMany();
  await prisma.recipe.deleteMany();
  await prisma.productVariant.deleteMany();
  await prisma.product.deleteMany();
  await prisma.material.deleteMany();
  await prisma.supplier.deleteMany();
  await prisma.warehouse.deleteMany();
  await prisma.user.deleteMany();

  console.log('🧹 Cleaned existing data.');

  // 1. Create Users
  const passwordHash = await bcrypt.hash('furnicore123', 10);

  const admin = await prisma.user.create({
    data: {
      email: 'admin@furnicore.kz',
      fullName: 'Арман Серикович (DEMO)',
      passwordHash,
      role: Role.OWNER,
      phone: '+7 (701) 100-20-30',
      isActive: true,
    },
  });

  const prodManager = await prisma.user.create({
    data: {
      email: 'production@furnicore.kz',
      fullName: 'Бауржан Ахметов (DEMO)',
      passwordHash,
      role: Role.PRODUCTION_MANAGER,
      phone: '+7 (777) 234-56-78',
      isActive: true,
    },
  });

  const whManager = await prisma.user.create({
    data: {
      email: 'warehouse@furnicore.kz',
      fullName: 'Даулет Касымов (DEMO)',
      passwordHash,
      role: Role.WAREHOUSE_MANAGER,
      phone: '+7 (705) 987-65-43',
      isActive: true,
    },
  });

  const salesManager = await prisma.user.create({
    data: {
      email: 'sales@furnicore.kz',
      fullName: 'Айгерим Нурланова (DEMO)',
      passwordHash,
      role: Role.SALES_MANAGER,
      phone: '+7 (771) 555-44-33',
      isActive: true,
    },
  });

  const worker = await prisma.user.create({
    data: {
      email: 'worker@furnicore.kz',
      fullName: 'Кайрат Омаров (DEMO)',
      passwordHash,
      role: Role.WORKER,
      phone: '+7 (702) 111-22-33',
      isActive: true,
    },
  });

  console.log('👤 Users created.');

  // 2. Exactly TWO Warehouses
  const wh1 = await prisma.warehouse.create({
    data: {
      code: 'WH-1',
      name: 'Склад №1 — Сырье и материалы',
      type: WarehouseType.RAW_MATERIALS,
      description: 'Основной материальный склад: плитные материалы, массив, фурнитура, ЛКМ, ткани, пенополиуретан',
      address: 'г. Алматы, Илийский тракт, 14, Ангар А',
    },
  });

  const wh2 = await prisma.warehouse.create({
    data: {
      code: 'WH-2',
      name: 'Склад №2 — Готовая продукция',
      type: WarehouseType.FINISHED_PRODUCTS,
      description: 'Склад готовых изделий: шкафы, столы, кровати, кухни, диваны, зона отгрузки и клиентского резерва',
      address: 'г. Алматы, Илийский тракт, 14, Секция В',
    },
  });

  console.log('🏢 Warehouses WH-1 and WH-2 created.');

  // 3. Suppliers
  const supTimber = await prisma.supplier.create({
    data: {
      name: 'ТОО "Тимбер Азия"',
      contactPerson: 'Сергей Николаев',
      phone: '+7 (727) 312-44-55',
      email: 'sales@timberasia.kz',
      address: 'г. Алматы, пр. Суюнбая, 261',
    },
  });

  const supHardware = await prisma.supplier.create({
    data: {
      name: 'ТОО "Blum & Фитинг KZ"',
      contactPerson: 'Елена Ким',
      phone: '+7 (727) 299-88-77',
      email: 'order@fitting.kz',
      address: 'г. Алматы, ул. Рыскулова, 143',
    },
  });

  const supFabrics = await prisma.supplier.create({
    data: {
      name: 'ТОО "SilkWay Textiles"',
      contactPerson: 'Мадина Султанова',
      phone: '+7 (701) 456-78-90',
      email: 'info@silkway-textile.kz',
      address: 'г. Шымкент, ул. Жибек Жолы, 88',
    },
  });

  // 4. Raw Materials (Warehouse 1)
  const materialsData = [
    { sku: 'MAT-WOD-001', name: 'Массив дуба 50мм (сухой калиброванный)', category: MaterialCategory.WOOD, unit: 'м³', minStockLevel: 5, purchaseCostKZT: 380000, supplierId: supTimber.id, stock: 12.5 },
    { sku: 'MAT-WOD-002', name: 'Массив сосны 40мм обрезной', category: MaterialCategory.WOOD, unit: 'м³', minStockLevel: 8, purchaseCostKZT: 145000, supplierId: supTimber.id, stock: 18.0 },
    { sku: 'MAT-MDF-001', name: 'МДФ влагостойкий 16мм Kronospan 2800x2070', category: MaterialCategory.MDF, unit: 'лист', minStockLevel: 40, purchaseCostKZT: 14200, supplierId: supTimber.id, stock: 85 },
    { sku: 'MAT-MDF-002', name: 'МДФ шлифованный 18мм Kastamonu 2800x2070', category: MaterialCategory.MDF, unit: 'лист', minStockLevel: 30, purchaseCostKZT: 16500, supplierId: supTimber.id, stock: 45 },
    { sku: 'MAT-CHP-001', name: 'ЛДСП Egger Дуб Галифакс натуральный 18мм', category: MaterialCategory.CHIPBOARD, unit: 'лист', minStockLevel: 50, purchaseCostKZT: 19800, supplierId: supTimber.id, stock: 32 }, // Low stock!
    { sku: 'MAT-CHP-002', name: 'ЛДСП Lamarty Белый базовый 16мм', category: MaterialCategory.CHIPBOARD, unit: 'лист', minStockLevel: 60, purchaseCostKZT: 11500, supplierId: supTimber.id, stock: 110 },
    { sku: 'MAT-PLY-001', name: 'Фанера березовая ФСФ 15мм сорт 2/4', category: MaterialCategory.PLYWOOD, unit: 'лист', minStockLevel: 25, purchaseCostKZT: 9800, supplierId: supTimber.id, stock: 40 },
    { sku: 'MAT-SCR-001', name: 'Конфирматы 7х50мм оцинкованные', category: MaterialCategory.HARDWARE_SCREWS, unit: 'упак (1000шт)', minStockLevel: 10, purchaseCostKZT: 4500, supplierId: supHardware.id, stock: 24 },
    { sku: 'MAT-HNG-001', name: 'Петля Blum CLIP top BLUMOTION 110° с доводчиком', category: MaterialCategory.HARDWARE_HINGES, unit: 'шт', minStockLevel: 150, purchaseCostKZT: 1650, supplierId: supHardware.id, stock: 340 },
    { sku: 'MAT-HND-001', name: 'Ручка мебельная скоба 160мм Черный матовый', category: MaterialCategory.HARDWARE_HANDLES, unit: 'шт', minStockLevel: 100, purchaseCostKZT: 1200, supplierId: supHardware.id, stock: 80 }, // Low stock!
    { sku: 'MAT-RAL-001', name: 'Направляющие скрытого монтажа Blum Tandem 500мм', category: MaterialCategory.HARDWARE_RAILS, unit: 'компл', minStockLevel: 40, purchaseCostKZT: 6900, supplierId: supHardware.id, stock: 75 },
    { sku: 'MAT-GLU-001', name: 'Клей столярный Titebond II Premium Wood Glue', category: MaterialCategory.GLUE, unit: 'канистра (10л)', minStockLevel: 6, purchaseCostKZT: 32000, supplierId: supTimber.id, stock: 14 },
    { sku: 'MAT-PNT-001', name: 'Эмаль полиуретановая Renner шелковисто-матовая', category: MaterialCategory.PAINT, unit: 'кг', minStockLevel: 30, purchaseCostKZT: 7800, supplierId: supTimber.id, stock: 65 },
    { sku: 'MAT-VRN-001', name: 'Лак полиуретановый Sayerlack полуглянцевый', category: MaterialCategory.VARNISH, unit: 'кг', minStockLevel: 20, purchaseCostKZT: 8400, supplierId: supTimber.id, stock: 35 },
    { sku: 'MAT-FAB-001', name: 'Велюр мебельный антикоготь Teddy Emerald', category: MaterialCategory.FABRIC, unit: 'пог. м', minStockLevel: 50, purchaseCostKZT: 4900, supplierId: supFabrics.id, stock: 120 },
    { sku: 'MAT-FOM-001', name: 'Пенополиуретан высокоэластичный HR 3535 (100мм)', category: MaterialCategory.FOAM, unit: 'лист', minStockLevel: 20, purchaseCostKZT: 13500, supplierId: supFabrics.id, stock: 15 }, // Low stock!
  ];

  const createdMaterials: Record<string, any> = {};

  for (const mat of materialsData) {
    const { stock, ...mProps } = mat;
    const material = await prisma.material.create({
      data: mProps,
    });
    createdMaterials[mat.sku] = material;

    // Create StockBalance in Warehouse 1 (Raw Materials)
    await prisma.stockBalance.create({
      data: {
        warehouseId: wh1.id,
        materialId: material.id,
        currentStock: stock,
        reservedStock: 0,
        minLevel: mat.minStockLevel,
        lastCountedAt: new Date(),
      },
    });

    // Record initial receipt movement
    await prisma.stockMovement.create({
      data: {
        movementNumber: `MOV-WH1-${Math.floor(1000 + Math.random() * 9000)}`,
        type: MovementType.RECEIPT,
        warehouseId: wh1.id,
        materialId: material.id,
        quantity: stock,
        unit: mat.unit,
        unitCostKZT: mat.purchaseCostKZT,
        totalCostKZT: stock * mat.purchaseCostKZT,
        referenceNumber: 'DEMO-INITIAL-STOCK',
        notes: 'Начальный остаток на Складе №1 (Сырье)',
        createdById: whManager.id,
      },
    });
  }

  console.log(`📦 Created ${materialsData.length} raw materials on Warehouse 1.`);

  // 5. Finished Products (Warehouse 2)
  const productsData = [
    {
      sku: 'PRD-WRD-001',
      name: 'Шкаф 3-дверный "Nordic Loft" с зеркалом',
      category: ProductCategory.WARDROBE,
      dimensions: '2200x1500x600 мм',
      description: 'Корпус ЛДСП Дуб Галифакс, фасады МДФ белый матовый, петли с доводчиком, зеркальная средняя створка.',
      productionCostKZT: 145000,
      salePriceKZT: 265000,
      currentStock: 6,
      reservedStock: 2,
    },
    {
      sku: 'PRD-TBL-001',
      name: 'Стол обеденный "Almaty Oak" раскладной',
      category: ProductCategory.TABLE,
      dimensions: '1600(2100)x900x760 мм',
      description: 'Столешница из массива дуба под матовым лаком, металлическое подстолье с порошковой покраской.',
      productionCostKZT: 98000,
      salePriceKZT: 185000,
      currentStock: 12,
      reservedStock: 3,
    },
    {
      sku: 'PRD-BED-001',
      name: 'Кровать двуспальная "Comfort Prime 180" с подъемным механизмом',
      category: ProductCategory.BED,
      dimensions: '2150x1920x1100 мм (спальное место 180x200)',
      description: 'Мягкое изголовье в велюре Teddy Emerald, ортопедическое основание, вместительный бельевой ящик.',
      productionCostKZT: 165000,
      salePriceKZT: 310000,
      currentStock: 4,
      reservedStock: 1,
    },
    {
      sku: 'PRD-KTC-001',
      name: 'Кухонный гарнитур угловой "Astana Mod" 3.2м',
      category: ProductCategory.KITCHEN,
      dimensions: '3200x1800x2300 мм',
      description: 'Фасады МДФ эмаль soft-touch, фурнитура Blum Tandembox, подсветка рабочей зоны, влагостойкая столешница 38мм.',
      productionCostKZT: 420000,
      salePriceKZT: 780000,
      currentStock: 2,
      reservedStock: 1,
    },
    {
      sku: 'PRD-SOF-001',
      name: 'Диван 3-местный прямой "Nomad Lounge"',
      category: ProductCategory.SOFA,
      dimensions: '2350x1050x880 мм',
      description: 'Каркас из березовой фанеры и бруса, наполнитель HR3535 + независимый пружинный блок, обивка велюр.',
      productionCostKZT: 175000,
      salePriceKZT: 340000,
      currentStock: 5,
      reservedStock: 0,
    },
  ];

  const createdProducts: Record<string, any> = {};

  for (const prod of productsData) {
    const { currentStock, reservedStock, ...pProps } = prod;
    const product = await prisma.product.create({
      data: pProps,
    });
    createdProducts[prod.sku] = product;

    // Create Product Variant
    await prisma.productVariant.create({
      data: {
        productId: product.id,
        sku: `${prod.sku}-VAR1`,
        name: `${prod.name} — Стандарт`,
        dimensions: prod.dimensions,
        colorVariant: 'Базовый',
        extraPriceKZT: 0,
      },
    });

    // Create StockBalance in Warehouse 2 (Finished Products)
    await prisma.stockBalance.create({
      data: {
        warehouseId: wh2.id,
        productId: product.id,
        currentStock,
        reservedStock,
        minLevel: 2,
        lastCountedAt: new Date(),
      },
    });

    // Record stock receipt on WH-2
    await prisma.stockMovement.create({
      data: {
        movementNumber: `MOV-WH2-${Math.floor(1000 + Math.random() * 9000)}`,
        type: MovementType.RECEIPT,
        warehouseId: wh2.id,
        productId: product.id,
        quantity: currentStock,
        unit: 'шт',
        unitCostKZT: prod.productionCostKZT,
        totalCostKZT: currentStock * prod.productionCostKZT,
        referenceNumber: 'DEMO-PRODUCTION-IN',
        notes: 'Приемка готовой продукции из цеха на Склад №2',
        createdById: whManager.id,
      },
    });
  }

  console.log(`🛋️ Created ${productsData.length} finished products on Warehouse 2.`);

  // 6. Recipe (Bill of Materials) for Wardrobe
  const wardrobe = createdProducts['PRD-WRD-001'];
  if (wardrobe) {
    const recipeWardrobe = await prisma.recipe.create({
      data: {
        productId: wardrobe.id,
        name: 'Техкарта: Шкаф 3-дверный Nordic Loft',
        version: '1.2',
        laborHours: 8.5,
        notes: 'Норма расхода материалов на 1 изделие согласно стандарту ГОСТ 16371-2014',
      },
    });

    await prisma.recipeItem.createMany({
      data: [
        { recipeId: recipeWardrobe.id, materialId: createdMaterials['MAT-CHP-001'].id, quantityRequired: 3.5, unit: 'лист' },
        { recipeId: recipeWardrobe.id, materialId: createdMaterials['MAT-MDF-001'].id, quantityRequired: 1.5, unit: 'лист' },
        { recipeId: recipeWardrobe.id, materialId: createdMaterials['MAT-HNG-001'].id, quantityRequired: 12, unit: 'шт' },
        { recipeId: recipeWardrobe.id, materialId: createdMaterials['MAT-HND-001'].id, quantityRequired: 3, unit: 'шт' },
        { recipeId: recipeWardrobe.id, materialId: createdMaterials['MAT-SCR-001'].id, quantityRequired: 0.1, unit: 'упак' },
      ],
    });

    // 7. Production Order
    await prisma.productionOrder.create({
      data: {
        orderNumber: 'PRD-2026-0041',
        productId: wardrobe.id,
        recipeId: recipeWardrobe.id,
        plannedQuantity: 4,
        completedQuantity: 2,
        status: ProductionStatus.IN_PROGRESS,
        plannedStartDate: new Date('2026-11-01'),
        plannedEndDate: new Date('2026-11-08'),
        actualStartDate: new Date('2026-11-02'),
        supervisorId: prodManager.id,
        totalActualCostKZT: 290000,
        notes: 'Партия по заказу ТОО "Комфорт Дом"',
      },
    });

    await prisma.productionOrder.create({
      data: {
        orderNumber: 'PRD-2026-0042',
        productId: createdProducts['PRD-TBL-001'].id,
        plannedQuantity: 8,
        completedQuantity: 0,
        status: ProductionStatus.PLANNED,
        plannedStartDate: new Date('2026-11-10'),
        plannedEndDate: new Date('2026-11-18'),
        supervisorId: prodManager.id,
        notes: 'Пополнение складского буфера столов к сезону',
      },
    });
  }

  // 8. Customers & Sales Orders
  const customer1 = await prisma.customer.create({
    data: {
      name: 'Ерлан Сагындыков',
      companyName: 'ТОО "Interior Project KZ"',
      phone: '+7 (707) 800-90-10',
      email: 'erlan@interior.kz',
      address: 'г. Алматы, мкр. Самал-2, д. 45',
    },
  });

  const customer2 = await prisma.customer.create({
    data: {
      name: 'Гульнара Идрисова',
      phone: '+7 (747) 123-45-67',
      email: 'gulnara.idrisova@gmail.com',
      address: 'г. Алматы, ул. Достык, 118, кв. 42',
    },
  });

  const salesOrder1 = await prisma.salesOrder.create({
    data: {
      orderNumber: 'ORD-2026-0089',
      customerId: customer1.id,
      status: OrderStatus.CONFIRMED,
      totalAmountKZT: 1470000,
      depositAmountKZT: 800000,
      discountAmountKZT: 50000,
      deliveryAddress: 'г. Алматы, пр. Аль-Фараби, 77/8',
      createdById: salesManager.id,
      notes: 'Предоплата 50% получена через Kaspi Pay. Доставка запланирована на 15 ноября.',
    },
  });

  await prisma.salesOrderItem.createMany({
    data: [
      {
        salesOrderId: salesOrder1.id,
        productId: createdProducts['PRD-WRD-001'].id,
        quantity: 2,
        unitPriceKZT: 265000,
        totalPriceKZT: 530000,
      },
      {
        salesOrderId: salesOrder1.id,
        productId: createdProducts['PRD-BED-001'].id,
        quantity: 1,
        unitPriceKZT: 310000,
        totalPriceKZT: 310000,
      },
      {
        salesOrderId: salesOrder1.id,
        productId: createdProducts['PRD-TBL-001'].id,
        quantity: 3,
        unitPriceKZT: 185000,
        totalPriceKZT: 555000,
      },
    ],
  });

  // 9. Monthly Expenses (Finance)
  const expensesData = [
    { num: 'EXP-2026-101', cat: ExpenseCategory.RENT, amount: 850000, desc: 'Аренда цеха и складов (ноябрь)', payee: 'ТОО "ПромКомплекс"' },
    { num: 'EXP-2026-102', cat: ExpenseCategory.ELECTRICITY, amount: 245000, desc: 'Электроэнергия станков ЧПУ и цеха', payee: 'АО "Алатау Жарык Компаниясы"' },
    { num: 'EXP-2026-103', cat: ExpenseCategory.GAS, amount: 95000, desc: 'Отопление производственных помещений', payee: 'АО "КазТрансГаз Аймак"' },
    { num: 'EXP-2026-104', cat: ExpenseCategory.PAYROLL, amount: 2450000, desc: 'Заработная плата мастеров цеха (аванс)', payee: 'ФОТ Производство' },
    { num: 'EXP-2026-105', cat: ExpenseCategory.TRANSPORT, amount: 160000, desc: 'Доставка материалов и отгрузка заказов', payee: 'ИП "ТрансЛогистик"' },
    { num: 'EXP-2026-106', cat: ExpenseCategory.REPAIRS, amount: 85000, desc: 'Замена фрез и плановое ТО форматно-раскроечного станка', payee: 'ТОО "СтанкоСервис"' },
  ];

  for (const exp of expensesData) {
    await prisma.expense.create({
      data: {
        expenseNumber: exp.num,
        category: exp.cat,
        amountKZT: exp.amount,
        paymentDate: new Date('2026-11-03'),
        description: exp.desc,
        payee: exp.payee,
        createdById: admin.id,
      },
    });
  }

  console.log('💰 Created initial monthly expenses.');
  console.log('✅ FurniCore ERP DEMO seed complete!');
}

main()
  .catch((e) => {
    console.error('❌ Error seeding database:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
