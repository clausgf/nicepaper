from typing import Annotated, Tuple
import niceview
from pydantic import BaseModel, Field

# Curated CLDR patterns for date/time selects.
_SHORT_DATE_FORMATS = ['dd.MM.yy', 'dd.MM.yyyy', 'yyyy-MM-dd', 'MM/dd/yy', 'MM/dd/yyyy', 'dd/MM/yyyy']
_LONG_DATE_FORMATS = ['EEEE, dd.MM.yyyy', 'EEEE, dd. MMMM yyyy', 'EEEE, MMMM d, yyyy', 'yyyy-MM-dd']
_TIME_FORMATS = ['HH:mm', 'HH:mm:ss', 'hh:mm a', 'h:mm a']


class GlobalConfig(BaseModel):
    """Settings shared by all screens in a project.

    Field labels: niceview auto-generates one from the field name
    (sentence case, e.g. font_name -> "Font name") wherever that's already
    right, so most fields below carry no explicit `title`. An explicit
    `title` only appears where auto-generation gets it wrong -- 'ical'
    doesn't capitalize into 'iCal', and a joined compound like
    'homeassistant'/'roomcalendar' can't be split into words at all -- or
    to drop a homeassistant_*/roomcalendar_* field's own redundant prefix,
    since its section heading already says it.
    """
    ical_error: Annotated[str,
            Field(title="iCal error",
                  description="Text shown on a display when the fetch from the booking system fails, e.g. 'Error fetching calendar data'."),
        ] = "Error fetching calendar data"
    ical_retry_min_s: Annotated[int,
            Field(title="iCal retry min s",
                  description="Backoff after a failed booking system fetch. Starts at this many seconds and doubles per consecutive failure."),
        ] = 60
    ical_retry_max_s: Annotated[int,
            Field(title="iCal retry max s",
                  description="Upper cap for the booking system fetch backoff, in seconds."),
        ] = 1800
    current_appointment: Annotated[str,
            Field(description="Text shown on a display for the current appointment."),
        ] = "Current appointment"
    no_appointments: Annotated[str,
            Field(description="Text shown on a display when there are no appointments."),
        ] = "No appointments"
    next_appointment: Annotated[str,
            Field(description="Text shown on a display for the next appointment."),
        ] = "Next appointment"
    further_appointments: Annotated[str,
            Field(description="Text shown on a display for further appointments."),
        ] = "Further appointments"
    roomcalendar_date_format_long: Annotated[str,
            Field(title="Date format (long, for heading)",
                  description="Date format for the room calendar (long form)."),
            niceview.Field(widget_type='ui.select', options=_LONG_DATE_FORMATS)
        ] = "EEEE, dd.MM.yyyy"
    roomcalendar_date_format_short: Annotated[str,
            Field(title="Date format (short, for appointments)", description="Date format for the room calendar (short form)."),
            niceview.Field(widget_type='ui.select', options=_SHORT_DATE_FORMATS)
        ] = "dd.MM.yy"
    roomcalendar_time_format: Annotated[str,
            Field(title="Time format (room calendar)", description="Time format for the room calendar."),
            niceview.Field(widget_type='ui.select', options=_TIME_FORMATS)
        ] = "HH:mm"

    wind_speed_unit: Annotated[str, Field(
            description=
                "Unit for wind speed: kmh, ms, mph or kn (knots). Open-Meteo is "
                "always fetched in km/h and converted locally, so changing this "
                "needs no refetch."),
            niceview.Field(widget_type='ui.select', options=['kmh', 'ms', 'mph', 'kn'])
        ] = "kmh"
    weather_update_interval_s: Annotated[int,
            Field(description="How often to update the weather data, in seconds."),
        ] = 900
    weather_retry_min_s: Annotated[int,
            Field(description="Minimum backoff after a failed weather fetch, in seconds."),
        ] = 60
    weather_retry_max_s: Annotated[int,
            Field(description="Upper cap for the weather-fetch backoff, in seconds."),
        ] = 1800
    weather_error: Annotated[str,
            Field(description="Text shown on a display when there is an error fetching weather data."),
            niceview.Field(hint="'{code}' is the failure reason (e.g. '401', 'timeout', 'conn').")
        ] = "Error fetching weather data"
    weather_stale_notice: Annotated[str,
            Field(description="Marker shown when serving cached data during an outage."),
            niceview.Field(hint="'{time}' is the last successful update. Empty to hide.")
        ] = "as of {time}"

    image_error: Annotated[str,
            Field(description="Text shown on a display when there is an error loading an image."),
            niceview.Field(hint="Error message, e.g. 'Error loading image'")
        ] = "Error loading image"
    image_retry_min_s: Annotated[int,
            Field(description="Backoff after a failed image load starts at this many seconds and doubles per consecutive failure."),
            niceview.Field(hint="Minimum backoff in seconds, e.g. 60")
        ] = 60
    image_retry_max_s: Annotated[int,
            Field(description="Upper cap for the image-load backoff, in seconds."),
            niceview.Field(hint="Maximum backoff in seconds, e.g. 1800")
        ] = 1800

    # Home Assistant connection settings belong to ProjectConfig.
    homeassistant_update_interval_s: Annotated[int,
            Field(title="Update interval s", description="How long a fetched entity state is reused before Home Assistant is asked again."),
            niceview.Field(hint="Update interval in seconds, e.g. 300")
        ] = 300
    homeassistant_retry_min_s: Annotated[int,
            Field(title="Retry min s", description="Backoff after a failed Home Assistant fetch starts at this many seconds and doubles per consecutive failure."),
            niceview.Field(hint="Minimum backoff in seconds, e.g. 60")
        ] = 60
    homeassistant_retry_max_s: Annotated[int,
            Field(title="Retry max s", description="Upper cap for the Home Assistant fetch backoff, in seconds."),
            niceview.Field(hint="Maximum backoff in seconds, e.g. 1800")
        ] = 1800
    homeassistant_error: Annotated[str,
            Field(title="Error message", description="Text shown on a display when there is an error fetching data from Home Assistant."),
            niceview.Field(hint="Error message, e.g. 'HA error ({code})'")
        ] = "HA error ({code})"
    homeassistant_stale_notice: Annotated[str,
            Field(title="Stale notice", description="Marker shown on a display when serving a cached value during an outage."),
            niceview.Field(hint="Stale notice, e.g. 'as of {time}'")
        ] = "as of {time}"

    locale: Annotated[str,
            Field(description="Locale for the display."),
            niceview.Field(hint="POSIX/Unix Locale identifier, e.g. 'de_DE.utf8'")
        ] = 'de_DE.utf8'
    timezone: Annotated[str,
            Field(description="Timezone for the display."),
            niceview.Field(hint="IANA Timezone, e.g. 'Europe/Berlin'")
        ] = 'Europe/Berlin'
    date_format: Annotated[str,
            Field(description="General date format."),
            niceview.Field(widget_type='ui.select', options=_SHORT_DATE_FORMATS)
        ] = 'dd.MM.yy'
    time_format: Annotated[str,
            Field(description="General time format."),
            niceview.Field(widget_type='ui.select', options=_TIME_FORMATS)
        ] = 'HH:mm'
    wakeup_margin_s: Annotated[int,
            Field(title="Wakeup margin s",
                  description="Added to a display's sleep time (Cache-Control max-age) to "
                              "compensate for imprecise device wakeup, so it wakes at or "
                              "after -- not before -- the intended update time (e.g. an "
                              "appointment's start/end)."),
        ] = 15

    font_name: Annotated[str,
            Field(description="Default font file name for widgets without their own font."),
            niceview.Field(hint="Font file name, e.g. Ubuntu-Regular.ttf")
        ] = "Ubuntu-Regular.ttf"
    font_size: Annotated[int,
            Field(description="Default font size for widgets without their own font."),
            niceview.Field(hint="Font size in points, e.g. 16")
        ] = 16

    @property
    def font(self) -> Tuple[str, int]:
        return (self.font_name, self.font_size)
