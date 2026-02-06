/**
 * SplitPane - Reusable split-view layout component
 * Desktop: side-by-side panels
 * Mobile: stacked with optional toggle
 */
import React from 'react';

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  leftWidth?: string;
  rightWidth?: string;
  showRight?: boolean;
  gap?: string;
  className?: string;
  stickyLeft?: boolean;
}

export const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
  leftWidth = '280px',
  rightWidth = '1fr',
  showRight = true,
  gap = '16px',
  className = '',
  stickyLeft = true,
}) => {
  return (
    <div
      className={`split-pane ${className}`}
      style={{
        display: 'grid',
        gridTemplateColumns: showRight ? `${leftWidth} ${rightWidth}` : leftWidth,
        gap,
        alignItems: 'start',
        height: '100%',
        minHeight: 0,
      }}
    >
      <div
        className="split-pane-left"
        style={{
          position: stickyLeft ? 'sticky' : 'relative',
          top: stickyLeft ? 0 : undefined,
          maxHeight: stickyLeft ? '100vh' : undefined,
          overflowY: stickyLeft ? 'auto' : undefined,
        }}
      >
        {left}
      </div>
      {showRight && (
        <div className="split-pane-right" style={{ minWidth: 0 }}>
          {right}
        </div>
      )}
    </div>
  );
};

/**
 * TriPane - Three-panel layout for master-detail-inspect patterns
 */
interface TriPaneProps {
  left: React.ReactNode;
  center: React.ReactNode;
  right?: React.ReactNode;
  leftWidth?: string;
  rightWidth?: string;
  gap?: string;
  className?: string;
}

export const TriPane: React.FC<TriPaneProps> = ({
  left,
  center,
  right,
  leftWidth = '280px',
  rightWidth = '380px',
  gap = '16px',
  className = '',
}) => {
  const columns = right
    ? `${leftWidth} 1fr ${rightWidth}`
    : `${leftWidth} 1fr`;

  return (
    <div
      className={`tri-pane ${className}`}
      style={{
        display: 'grid',
        gridTemplateColumns: columns,
        gap,
        alignItems: 'start',
        height: '100%',
        minHeight: 0,
      }}
    >
      <div
        className="tri-pane-left"
        style={{
          position: 'sticky',
          top: 0,
          maxHeight: '100vh',
          overflowY: 'auto',
        }}
      >
        {left}
      </div>
      <div className="tri-pane-center" style={{ minWidth: 0, overflow: 'auto' }}>
        {center}
      </div>
      {right && (
        <div
          className="tri-pane-right"
          style={{
            position: 'sticky',
            top: 0,
            maxHeight: '100vh',
            overflowY: 'auto',
          }}
        >
          {right}
        </div>
      )}
    </div>
  );
};

export default SplitPane;
