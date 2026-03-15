import React from 'react';

function TarotCardArt({ fortune }) {
  const imageUrl = fortune?.card_image_url;
  const isZh = fortune?.lang === 'zh';

  return (
    <div className="w-full max-w-[250px]">
      <div
        className="relative overflow-hidden border border-[rgba(255,191,60,0.22)] bg-[rgba(255,191,60,0.02)] p-3"
        style={{ boxShadow: '0 18px 40px rgba(0,0,0,0.24)' }}
      >
        <div className="mb-3 flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.16em] text-[#ffbf3c]">
          <span>RWS</span>
          <span>{String(fortune?.card_number ?? '').padStart(2, '0')}</span>
        </div>

        <div className="relative overflow-hidden border border-[rgba(255,191,60,0.18)] bg-[#050607]">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={fortune?.card || 'Tarot card'}
              className={`block h-[360px] w-full object-cover ${fortune?.is_reversed ? 'rotate-180' : ''}`}
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="flex h-[360px] items-center justify-center text-sm text-[#ffbf3c]/70">
              Tarot
            </div>
          )}

          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.12)_50%)] bg-[length:100%_4px]" />

          <div className="absolute left-3 top-3 border border-[rgba(255,191,60,0.35)] bg-[rgba(5,5,5,0.82)] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[#ffcf69]">
            {fortune?.is_reversed ? (isZh ? '逆位' : 'Reversed') : (isZh ? '正位' : 'Upright')}
          </div>
        </div>
      </div>
    </div>
  );
}

export default TarotCardArt;
