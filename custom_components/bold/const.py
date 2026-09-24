"""Constants for the Bold Smart Lock integration."""

from datetime import timedelta

DOMAIN = "bold"
MANUFACTURER = "Bold"

API_URL = "https://api.boldsmartlock.com"
OAUTH2_AUTHORIZE = "https://auth.boldsmartlock.com/authorize"
OAUTH2_TOKEN = f"{API_URL}/v2/oauth/token"

# Remote activation needs a user-level session. No scope parameter: Bold then grants
# every scope the client supports, while naming an unsupported one fails the login.
OAUTH2_LEVEL = "user"

UPDATE_INTERVAL = timedelta(minutes=5)
EVENT_LOOKBACK = timedelta(hours=1)
DEFAULT_ACTIVATION_TIME = 7  # seconds, used when Bold does not return one

EVENT_BOLD = "bold_event"
ACCESS_EVENT_TYPES = ("DeviceActivation", "DeviceDeactivation", "DeviceLocked")

DEVICE_TYPE_LOCK = "Lock"
DEVICE_TYPE_GATEWAY = "Gateway"
