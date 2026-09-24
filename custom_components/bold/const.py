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

UPDATE_INTERVAL = timedelta(minutes=5)
EVENT_LOOKBACK = timedelta(hours=1)
DEFAULT_ACTIVATION_TIME = 7  # seconds, used when Bold does not return one

EVENT_BOLD = "bold_event"
ACCESS_EVENT_TYPES = ("DeviceActivation", "DeviceDeactivation", "DeviceLocked")

DEVICE_TYPE_LOCK = "Lock"
DEVICE_TYPE_GATEWAY = "Gateway"
