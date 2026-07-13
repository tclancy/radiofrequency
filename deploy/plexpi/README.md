# TPMS slice-1 deploy on plexpi

Manual install ritual — plexpi does not have `itguy` deployment. Bluelinky and
fuelbot follow the same pattern (clone + venv + systemd unit under `pi`).

## Prereqs

1. RTL-SDR dongle plugged into plexpi USB, antenna facing the driveway.
2. `rtl_433` installed (`sudo apt install rtl-433`).
3. Confirm reception near the parked CX-9:

   ```bash
   rtl_433 -f 315000000 -R 156 -M level
   ```

   You should see periodic decoded events tagged `Abarth-124Spider`. If nothing
   arrives after a few minutes, walk closer to the vehicle or drive the car
   briefly to wake the sensors.

## Install

```bash
ssh -i ~/.ssh/id_claude pi@192.168.68.54
sudo mkdir -p /var/lib/tpms /var/log/tpms
sudo chown pi:pi /var/lib/tpms /var/log/tpms

cd /home/pi
git clone https://github.com/tclancy/radiofrequency tpms
cd tpms
uv sync

mkdir -p ~/.config/systemd/user
cp deploy/plexpi/tpms-capture.service ~/.config/systemd/user/
cp deploy/plexpi/tpms-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tpms-api.service
systemctl --user enable --now tpms-capture.service
loginctl enable-linger pi   # so units survive logout
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
| `TPMS_DB` | `/var/lib/tpms/tpms.sqlite3` | SQLite path (both services share) |
| `TPMS_LOW_PSI` | `30.0` | Threshold that sets `any_low: true` in `/latest` |
| `TPMS_STALE_SECONDS` | `900` | Reading is `stale: true` after this many seconds; `receiver_ok` flips false past the same window |
