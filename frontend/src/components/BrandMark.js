import React from 'react';

function BrandMark({ size = 'md', showWordmark = false, subtitle = '' }) {
  const isLarge = size === 'lg';
  const frame = isLarge ? 'h-[78px] w-[78px] rounded-[22px]' : 'h-10 w-10 rounded-[14px]';
  const wordmarkSize = isLarge ? 'text-[54px]' : 'text-[18px]';
  const gap = showWordmark ? (isLarge ? 'gap-5' : 'gap-3') : 'gap-0';

  return (
    <div className={`flex items-center ${gap}`}>
      <div
        className={`${frame} relative shrink-0 overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--surface-strong)]`}
      >
        <div className="absolute inset-0 bg-[linear-gradient(rgba(16,16,16,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(16,16,16,0.06)_1px,transparent_1px)] bg-[size:10px_10px]" />
        <div className="absolute left-0 top-0 h-5 w-5 bg-black" />
        <div className="absolute bottom-0 right-0 h-3.5 w-3.5 bg-black" />
        <div className="absolute inset-[18%] border border-[color:var(--line)]" />
        <div className="absolute inset-x-[24%] bottom-[20%] top-[20%] border-l border-r border-[color:var(--line-strong)]" />
        <div className="absolute inset-y-[24%] left-[20%] right-[20%] border-t border-b border-[color:var(--line)]" />
        <div className="absolute bottom-[16%] left-[18%] font-[var(--mono)] text-[11px] font-bold uppercase tracking-[0.3em] text-black">
          D
        </div>
      </div>

      {showWordmark ? (
        <div className="leading-none">
          <div className="panel-label">Daymark // Daily Trace System</div>
          <div className={`mt-2 font-semibold tracking-[-0.06em] text-[color:var(--text)] ${wordmarkSize}`}>
            Daymark
          </div>
          {subtitle ? (
            <div className="mt-2 max-w-[32rem] text-sm leading-6 text-[color:var(--muted)]">
              {subtitle}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default BrandMark;
