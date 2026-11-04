import type { Driver, TrackSector } from '../types';

interface TrackMapProps {
  sectors: TrackSector[];
  drivers: Driver[];
  activeEvent: string;
}

const sectorClass = (tone: TrackSector['tone']) => `track-line track-line--${tone}`;

export function TrackMap({ sectors, drivers, activeEvent }: TrackMapProps) {
  return (
    <section className="panel track-panel" aria-labelledby="track-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Circuit pulse</p>
          <h2 id="track-title">Where the race is moving</h2>
        </div>
        <span className="event-pill"><span className="event-dot" />{activeEvent}</span>
      </div>
      <div className="track-visual">
        <svg viewBox="0 0 560 320" role="img" aria-label="Illustrated circuit with driver positions and sector conditions">
          <defs>
            <filter id="car-glow" x="-70%" y="-70%" width="240%" height="240%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <linearGradient id="track-sheen" x1="0" x2="1">
              <stop offset="0" stopColor="#4a9dff" />
              <stop offset="0.5" stopColor="#86e7d2" />
              <stop offset="1" stopColor="#a89bff" />
            </linearGradient>
          </defs>
          <path className="track-shadow" d="M113 222 C46 176 87 93 186 104 C249 35 383 54 405 116 C488 133 498 224 421 250 C354 288 278 267 237 237 C189 269 142 253 113 222 Z" />
          <path className={sectorClass(sectors[0]?.tone ?? 'dry')} d="M113 222 C46 176 87 93 186 104 C216 74 253 62 293 66" />
          <path className={sectorClass(sectors[1]?.tone ?? 'neutral')} d="M293 66 C360 69 394 91 405 116 C488 133 498 224 421 250" />
          <path className={sectorClass(sectors[2]?.tone ?? 'dry')} d="M421 250 C354 288 278 267 237 237 C189 269 142 253 113 222" />
          <path className="track-core" d="M113 222 C46 176 87 93 186 104 C249 35 383 54 405 116 C488 133 498 224 421 250 C354 288 278 267 237 237 C189 269 142 253 113 222 Z" />
          <path className="start-line" d="M115 195 L144 177" />
          <text x="102" y="166" className="svg-label">START</text>
          <text x="217" y="86" className="svg-sector-label">S1</text>
          <text x="432" y="154" className="svg-sector-label">S2</text>
          <text x="311" y="272" className="svg-sector-label">S3</text>
          {drivers.slice(0, 5).map((driver, index) => {
            const points = [[180, 104], [337, 69], [436, 176], [350, 261], [189, 246]];
            const [x, y] = points[index];
            return (
              <g key={driver.number} className="car-marker" style={{ transform: `translate(${x}px, ${y}px)` }} filter="url(#car-glow)">
                <circle r="14" className={`car-marker__circle car-marker__circle--${driver.impact.tone}`} />
                <text textAnchor="middle" dominantBaseline="middle" className="car-marker__number">{driver.number}</text>
              </g>
            );
          })}
          <circle cx="281" cy="151" r="76" className="track-ambient" />
          <path d="M274 109 L308 109 L302 121 L307 132 L278 132 L278 116 Z" className="vsc-flag" />
        </svg>
        <div className="track-legend">
          {sectors.map((sector) => (
            <div className="track-legend__item" key={sector.id}>
              <span className={`legend-swatch legend-swatch--${sector.tone}`} />
              <span><strong>{sector.label}</strong><small>{sector.condition} · {sector.confidence}% confidence</small></span>
            </div>
          ))}
        </div>
      </div>
      <p className="panel-note">Track state is assembled from event status and observations. It never presents inferred grip as a direct measurement.</p>
    </section>
  );
}
