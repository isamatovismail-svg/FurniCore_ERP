import React from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  className,
  variant = 'primary',
  size = 'md',
  icon,
  disabled,
  ...props
}) => {
  const baseClasses =
    'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed select-none';

  const variantClasses = {
    primary:
      'bg-furni-primary text-white hover:bg-furni-primary-hover focus:ring-furni-primary shadow-sm',
    secondary:
      'bg-furni-secondary text-white hover:bg-furni-secondary-hover focus:ring-furni-secondary shadow-sm',
    outline:
      'border border-furni-border text-furni-text hover:bg-white hover:border-furni-secondary focus:ring-furni-secondary bg-transparent',
    ghost:
      'text-furni-muted hover:text-furni-text hover:bg-black/5 focus:ring-furni-primary',
    danger:
      'bg-furni-danger text-white hover:bg-red-700 focus:ring-furni-danger shadow-sm',
  };

  const sizeClasses = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  return (
    <button
      className={cn(baseClasses, variantClasses[variant], sizeClasses[size], className)}
      disabled={disabled}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </button>
  );
};
