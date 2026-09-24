# Bold Smart Lock for Home Assistant

Control [Bold](https://boldsmartlock.com) smart locks from Home Assistant through the
official Bold cloud API. Remote operation needs a **Bold Connect**.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bastichelaar&repository=homeassistant-bold&category=integration)

## What you get

Per lock:

| Entity | Notes |
|---|---|
| `lock.<name>` | *Unlock* activates the lock for its activation time, after which it reports locked again. *Lock* ends a running activation. `changed_by` shows who last used the lock. |
| Battery | Percentage (or Bold's status text if it doesn't send a number). |
| Battery last measured | Diagnostic. |
| Bold Connect signal / last seen | Diagnostic, from the gateway the lock uses. |
| Firmware update required | On when the firmware is older than Bold requires. |

Every new lock event (activation, deactivation, bolt status) is also fired as a
`bold_event` on the event bus, with `type`, `device_id`, `device_name`, `user` and `time`.
Use it in automations, e.g. *notify me when someone opens the front door*.

Data is polled every 5 minutes. A lock you operate from Home Assistant updates immediately.

## Installation

1. In HACS, add this repository as a **custom repository** (category *Integration*), or use
   the button above. Install **Bold Smart Lock** and restart Home Assistant.
2. **Request an OAuth client from Bold.** API keys cannot open locks, so you need a
   client ID and secret, which Bold gives out free of charge:
   [request a custom client](https://sesamsolutions.gitlab.io/public-documentation/integration/oauth-authentication.html).
   Use this as the redirect URI:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
3. In Home Assistant go to **Settings → Devices & services → Add integration → Bold Smart
   Lock**. Enter the client ID and secret, then log in with your Bold account.

### Coming from lwestenberg/homeassistant_bold

This integration uses the same `bold` domain and the same unique IDs for locks, so it
replaces the old one. Your existing lock entity and its automations stay as they are.
Remove the old repository from HACS first, then install this one.

## Troubleshooting

- **"Bold could not operate the lock (…)"**: the text in brackets is Bold's own error code.
  Mostly the Bold Connect is offline or out of range of the lock.
- **Too many activations**: Bold limits the number of activations per user per day.
- **Login does not return to Home Assistant**: check the redirect URI of your Bold client;
  it must be exactly `https://my.home-assistant.io/redirect/oauth`.
- Download diagnostics from the device page when reporting an issue. Tokens, names and
  e-mail addresses are removed from it.

## Development

```sh
uv venv && uv pip install -r requirements_test.txt
uv run pytest
```

## Credits

Thanks to [lwestenberg/homeassistant_bold](https://github.com/lwestenberg/homeassistant_bold),
the original Bold integration, which this one replaces.

This project is not affiliated with Bold or Sesam Solutions.
