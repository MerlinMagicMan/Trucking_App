/**
 * Forward-look timeline component
 * Shows 24-48 hour projection of trip
 */
import type { ForwardLook } from '../types/models';

interface TimelineProps {
  forwardLook: ForwardLook;
}

export default function Timeline({ forwardLook }: TimelineProps) {
  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'current':
        return '📍';
      case 'arrive_pickup':
        return '🚚';
      case 'depart_pickup':
        return '➡️';
      case 'arrive_delivery':
        return '🏭';
      case 'available_reload':
        return '🔄';
      default:
        return '•';
    }
  };

  return (
    <div className="timeline">
      <h3>Forward Look ({forwardLook.horizon_hours} Hours)</h3>

      <div className="timeline-events">
        {forwardLook.events.map((event, idx) => (
          <div key={idx} className={`timeline-event event-${event.event_type}`}>
            <div className="event-icon">{getEventIcon(event.event_type)}</div>
            <div className="event-content">
              <div className="event-time">{formatTime(event.timestamp)}</div>
              <div className="event-description">{event.description}</div>
              {event.location && (
                <div className="event-location">{event.location}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {forwardLook.reload_market_assessment && (
        <div className="market-assessment">
          <h4>Market Outlook</h4>
          <p>{forwardLook.reload_market_assessment}</p>
        </div>
      )}
    </div>
  );
}
