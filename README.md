# Bold Smart Lock for Home Assistant

Control [Bold](https://boldsmartlock.com) smart locks from Home Assistant through the
official Bold cloud API. Remote operation needs a **Bold Connect**.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bastichelaar&repository=homeassistant-bold&category=integration)

## What you get

Per lock:

| Entity | Notes |
|---|---|
| `lock.<name>` | *Unlock* activates the lock for its activation time, after which it reports locked again. *Lock* ends a running activation. `changed_by` shows who last used the lock. |
| `event.<name>_activity` | Fires on every activation (with `method`: Pin/Button/Ble/Mqtt/Matter, `result`, `user`, `pin_name`), failed activation, deactivation, bolt locked/unlocked and tamper alert (vibration, rotations, wrong PIN codes). |
| Battery | Percentage (or Bold's status text if it doesn't send a number). |
| Last locked | Locks with lock detection (Bold Elite) only. |
| Temperature, battery voltage (idle / under load) | Diagnostic, from the status report the lock sends periodically. |
| Battery last measured, Bold Connect signal / last seen | Diagnostic. |
| Firmware update required | On when the firmware is older than Bold requires. |

### Lock status (Bold Elite)

Locks with lock detection report whether the bolt is actually thrown, so the lock entity
shows **locked**, **unlocked** or **unknown** (for instance when the unlock direction isn't
set in the Bold app). On a Bold SX, which can't detect this, the lock shows unlocked only
during an activation.

Lock status comes from polling. The default interval is 5 minutes; set it (down to 30
seconds) under **Configure** on the integration.

### Keep active

Locks with keep-active mode can stay active until a set time:

```yaml
action: bold.activate
target:
  entity_id: lock.front_door
data:
  keep_active_until: "2026-09-24 18:00:00"
```

Without `keep_active_until` this is a normal activation, the same as *Unlock*.

### Events on the bus

Every event above is also fired as `bold_event` on the event bus, with `type` (Bold's own
event type), `device_id`, `device_name`, `user`, `time` and the extra fields.

### Not possible through the API

Bold's public API is read-only for lock settings (night lock, follow-in protection,
button auto-disable, tamper sensitivity, …): changing them needs the Bold app. The
alerts the app shows are available here as activity events.

The Bold Elite also supports Matter. Paired with Home Assistant's Matter integration it
gives local lock status and control, without the cloud. Bold calls it experimental.

## Installation

1. In HACS, add this repository as a **custom repository** (category *Integration*), or use
   the button above. Install **Bold Smart Lock** and restart Home Assistant.
2. Go to **Settings → Devices & services → Add integration → Bold Smart Lock** and log in
   with your Bold account. There are two ways to authorize:
   - **Home Assistant Cloud (easiest).** Nabu Casa has an OAuth client registered with Bold
     and offers it through account linking; Home Assistant shows it as an option
     automatically. **No Nabu Casa subscription or account is needed**, but the `cloud`
     integration must be loaded (it is part of `default_config`; otherwise add `cloud:` to
     `configuration.yaml`). You don't have to log in to it. Your Bold tokens are
     exchanged and refreshed through Nabu Casa's account-link server.
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
