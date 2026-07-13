# TPMS slice-1 deploy on plexpi

Manual install ritual — plexpi does not have `itguy` deployment. Bluelinky and
fuelbot follow the same pattern (clone + venv + systemd unit under `pi`).

Both units are `systemctl --user` units, so they inherit the `pi` user
identity automatically — no `User=`/`Group=` directives (which systemd rejects
in `--user` units).

## Prereqs

1. RTL-SDR dongle plugged into plexpi USB, antenna facing the driveway.
2. `rtl_433` installed (`sudo apt install rtl-433`).
3. Confirm reception near the parked CX-9:

   ```bash
   rtl_433 -M utc -f 315000000 -R 156 -M level
   ```

   You should see periodic decoded events tagged `Abarth-124Spider`. If nothing
   arrives after a few minutes, walk closer to the vehicle or drive the car
   briefly to wake the sensors. `-M utc` is important — without it, rtl_433
   emits system-local timestamps and the ingest daemon will skew every reading
   by the local UTC offset.

## Install

```bash
ssh -i ~/.ssh/id_claude pi@192.168.68.54

# Data and log directories live under $HOME so no sudo is needed and
# systemd --user units can write freely.
mkdir -p ~/.local/share/tpms ~/tpms-logs

cd ~
git clone https://github.com/tclancy/radiofrequency tpms
cd tpms
uv sync

mkdir -p ~/.config/systemd/user
cp deploy/plexpi/tpms-capture.service ~/.config/systemd/user/
cp deploy/plexpi/tpms-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tpms-api.service
systemctl --user enable --now tpms-capture.service
sudo loginctl enable-linger pi   # so --user units survive logout
```

## Verify

```bash
# Ingest capturing something
journalctl --user -u tpms-capture -f

# API responding
curl http://192.168.68.54:8090/api/vehicles
curl http://192.168.68.54:8090/api/vehicles/mazda-cx9/tpms/latest
curl http://192.168.68.54:8090/api/health
```

The first `latest` response is likely `{"readings": [], ...}` until the CX-9's
sensors wake up (parked sensors transmit ~once per 60 s, sometimes much less).
`/api/health` returns `receiver_ok: false` until the first reading lands.

## Sensor IDs on record

Slice-1 does not map sensor→corner (any-tire-low alerting only). The `sensors`
table populates automatically as new sensor IDs are seen — no manual seed.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TPMS_DB` | `~/.local/share/tpms/tpms.sqlite3` | SQLite path (both services share) |
| `TPMS_LOW_PSI` | `30.0` | Threshold that sets `any_low: true` in `/latest` |
| `TPMS_STALE_SECONDS` | `900` | Reading is `stale: true` after this many seconds; `receiver_ok` flips false past the same window |
