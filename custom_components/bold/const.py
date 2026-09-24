"""Constants for the Bold Smart Lock integration."""

from datetime import timedelta

DOMAIN = "bold"
MANUFACTURER = "Bold"

API_URL = "https://api.boldsmartlock.com"
OAUTH2_AUTHORIZE = "https://auth.boldsmartlock.com/authorize"
OAUTH2_TOKEN = f"{API_URL}/v2/oauth/token"

# No level/scope parameters: Bold defaults to a user-level session with every scope
# the client supports, which is what remote activation needs. Home Assistant Cloud
# account linking (Nabu Casa's own Bold client) builds its own authorize URL anyway.

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 300  # seconds
MIN_SCAN_INTERVAL = 30
# At startup, look back far enough to find the latest status report of each lock.
EVENT_LOOKBACK = timedelta(hours=24)
DEFAULT_ACTIVATION_TIME = 7  # seconds, used when Bold does not return one

EVENT_BOLD = "bold_event"
ACCESS_EVENT_TYPES = ("DeviceActivation", "DeviceDeactivation", "DeviceLocked")
TAMPER_EVENT_TYPES = (
    "DeviceTamperVibration",
    "DeviceTamperRotations",
    "DeviceTamperFaultyPin",
)
STATUS_EVENT_TYPE = "DeviceStatus"
EVENT_TYPES = (*ACCESS_EVENT_TYPES, *TAMPER_EVENT_TYPES, STATUS_EVENT_TYPE)

SERVICE_ACTIVATE = "activate"
ATTR_KEEP_ACTIVE_UNTIL = "keep_active_until"

DEVICE_TYPE_LOCK = "Lock"
DEVICE_TYPE_GATEWAY = "Gateway"
