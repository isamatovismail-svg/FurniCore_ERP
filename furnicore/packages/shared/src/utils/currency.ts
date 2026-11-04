/**
 * FurniCore ERP — KZT (Kazakhstani tenge) formatting utilities
 */

export function formatKZT(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '0 ₸';
  }
  const numeric = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('ru-KZ', {
    style: 'currency',
    currency: 'KZT',
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  })
    .format(numeric)
    .replace('KZT', '₸');
}

export function formatQuantity(qty: number | string, unit = 'шт'): string {
  const numeric = typeof qty === 'string' ? parseFloat(qty) : qty;
  return `${new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 2,
  }).format(numeric)} ${unit}`;
}
