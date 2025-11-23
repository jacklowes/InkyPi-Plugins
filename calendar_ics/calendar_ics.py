import logging
import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar
from plugins.base_plugin.base_plugin import BasePlugin
import recurring_ical_events

logger = logging.getLogger(__name__)

class CalendarICS(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        # Add custom settings if needed, though settings.html handles the UI
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("CalendarICS: Generating image...")
        ics_url = settings.get("ics_url")
        event_limit = int(settings.get("event_limit", 5))

        if not ics_url:
            raise RuntimeError("Please provide an ICS URL in the plugin settings.")

        try:
            response = requests.get(ics_url, timeout=10)
            response.raise_for_status()
            cal = Calendar.from_ical(response.content)
        except Exception as e:
            logger.error(f"Failed to fetch or parse ICS: {e}")
            raise RuntimeError(f"Failed to fetch calendar: {e}")

        events = []
        now = datetime.now(pytz.utc)
        # Look ahead 30 days
        end_date = now + timedelta(days=30)

        # Expand recurring events
        expanded_events = recurring_ical_events.of(cal).between(now, end_date)

        for component in expanded_events:
            summary = component.get('summary')
            start = component.get('dtstart')
            end = component.get('dtend')
            location = component.get('location')

            if start:
                dt_start = start.dt
                # Handle date objects (all-day events)
                if not isinstance(dt_start, datetime):
                    dt_start = datetime.combine(dt_start, datetime.min.time()).replace(tzinfo=pytz.utc)
                elif dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=pytz.utc)

                # Handle end time
                if end:
                    dt_end = end.dt
                    if not isinstance(dt_end, datetime):
                        dt_end = datetime.combine(dt_end, datetime.max.time()).replace(tzinfo=pytz.utc)
                    elif dt_end.tzinfo is None:
                        dt_end = dt_end.replace(tzinfo=pytz.utc)
                else:
                    # Default to 1 hour duration if no end time
                    dt_end = dt_start + timedelta(hours=1)

                # Filter: Keep if end time is in the future
                if dt_end > now:
                    events.append({
                        "summary": str(summary),
                        "start_time": dt_start,
                        "end_time": dt_end,
                        "location": str(location) if location else None,
                        "is_all_day": not isinstance(start.dt, datetime)
                    })

        # Sort by start time
        events.sort(key=lambda x: x['start_time'])
        
        # Limit number of events
        events = events[:event_limit]
        
        logger.info(f"CalendarICS: Found {len(events)} upcoming events.")

        # Determine density class for scaling
        count = len(events)
        if count <= 3:
            density_class = "density-low"
        elif count <= 6:
            density_class = "density-medium"
        else:
            density_class = "density-high"
            
        logger.info(f"CalendarICS: Event count: {count}, Density class: {density_class}")

        # Get dimensions from config
        # Reverting to hardcoded 800x480 as dynamic resolution caused issues for the user
        dimensions = (800, 480)
        
        logger.info(f"CalendarICS: Generating image with dimensions: {dimensions}")

        # Render image
        try:
            return self.render_image(
                dimensions=dimensions,
                html_file="calendar.html",
                css_file="style.css",
                template_params={
                    "events": events,
                    "updated_at": datetime.now().strftime("%H:%M"),
                    "plugin_settings": settings,
                    "density_class": density_class
                }
            )
        except Exception as e:
            logger.error(f"CalendarICS: Error rendering image: {e}")
            raise
