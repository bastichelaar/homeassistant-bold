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
2. Go to **Settings → Devices & services → Add integration → Bold Smart Lock** and log in
   with your Bold account. There are two ways to authorize:
   - **Home Assistant Cloud (easiest).** Nabu Casa has an OAuth client registered with Bold
     and offers it through account linking; Home Assistant shows it as an option
     automatically. This needs the `cloud` integration to be loaded (it is part of
     `default_config`; otherwise add `cloud:` to `configuration.yaml`).
   - **Your own OAuth client.** [Request a custom client](https://sesamsolutions.gitlab.io/public-documentation/integration/oauth-authentication.html)
     from Bold (free) with redirect URI `https://my.home-assistant.io/redirect/oauth`, and
     enter its client ID and secret as application credentials when asked.

API keys from the Bold Portal will not work: Bold does not allow them to open locks.

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
