import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

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

export function formatNumber(val: number | string): string {
  const numeric = typeof val === 'string' ? parseFloat(val) : val;
  return new Intl.NumberFormat('ru-RU').format(numeric);
}
