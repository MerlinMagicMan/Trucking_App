/**
 * PreviewBadge - Consistent badge for preview/beta features (PREVIEW-001)
 */
import React from 'react';

export type BadgeVariant = 'preview' | 'beta' | 'coming-soon' | 'premium';

interface PreviewBadgeProps {
  variant?: BadgeVariant;
  className?: string;
}

const BADGE_STYLES: Record<BadgeVariant, { bg: string; color: string; label: string }> = {
  preview: {
    bg: '#dbeafe',
    color: '#1e40af',
    label: 'Preview',
  },
  beta: {
    bg: '#fef3c7',
    color: '#92400e',
    label: 'Beta',
  },
  'coming-soon': {
    bg: '#f1f5f9',
    color: '#475569',
    label: 'Coming Soon',
  },
  premium: {
    bg: '#f3e8ff',
    color: '#7c3aed',
    label: 'Premium',
  },
};

export const PreviewBadge: React.FC<PreviewBadgeProps> = ({
  variant = 'preview',
  className = '',
}) => {
  const style = BADGE_STYLES[variant];

  return (
    <span
      className={`preview-badge ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        fontSize: '10px',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        padding: '2px 8px',
        borderRadius: '4px',
        backgroundColor: style.bg,
        color: style.color,
      }}
    >
      {style.label}
    </span>
  );
};

export default PreviewBadge;
