import type { RaceEvent } from '../types';

interface PulseTimelineProps {
  events: RaceEvent[];
}

export function PulseTimeline({ events }: PulseTimelineProps) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">The race story</p>
          <h2 id="timeline-title">What changed, in order</h2>
        </div>
        <span className="subtle-chip">Event time</span>
      </div>
      <div className="timeline-list">
        {events.map((event) => (
          <article key={event.id} className={`timeline-item timeline-item--${event.type} ${event.active ? 'timeline-item--active' : ''}`}>
            <time>{event.time}</time>
            <span className="timeline-node" aria-hidden="true" />
            <div>
              <div className="timeline-title-row"><h3>{event.title}</h3>{event.active && <span>active now</span>}</div>
              <p>{event.detail}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
