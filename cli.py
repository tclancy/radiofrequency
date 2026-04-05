#!/usr/bin/env python3
"""Control RF devices (e.g. Sofucor fans) via NodeMCU HTTP API.

Usage:
    python cli.py sofucor_fan bedroom speed1 --host 192.168.1.42
    python cli.py sofucor_fan living_room off --host nodemcu.local
"""
import sys

import click
import httpx

from src.device import DeviceProfile, build_packet

DEVICES_DIR = "devices"


@click.command()
@click.argument("device")
@click.argument("unit")
@click.argument("command")
@click.option("--host", default="nodemcu.local", show_default=True, help="NodeMCU hostname or IP")
@click.option("--port", default=80, show_default=True, help="NodeMCU HTTP port")
def cli(device: str, unit: str, command: str, host: str, port: int) -> None:
    """Send an RF command to a device via NodeMCU.

    \b
    DEVICE:  profile name  (e.g. sofucor_fan)
    UNIT:    unit name     (e.g. bedroom, living_room)
    COMMAND: button name   (e.g. speed1, speed2, speed3, off, light)
    """
    profile = DeviceProfile.load(f"{DEVICES_DIR}/{device}.yaml")

    if unit not in profile.units:
        available = ", ".join(sorted(profile.units))
        click.echo(f"Error: unknown unit '{unit}'. Available: {available}", err=True)
        sys.exit(1)

    if command not in profile.commands:
        available = ", ".join(sorted(profile.commands))
        click.echo(f"Error: unknown command '{command}'. Available: {available}", err=True)
        sys.exit(1)

    fan_number = profile.units[unit]["fan_number"]
    url = f"http://{host}:{port}/fan/{fan_number}/{command}"

    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        click.echo(f"Error: could not connect to {host}:{port}", err=True)
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        click.echo(f"Error: NodeMCU returned {exc.response.status_code} for {url}", err=True)
        sys.exit(1)

    packet = build_packet(profile, unit=unit, command=command)
    click.echo(f"OK  {command} → {device}/{unit}  [{packet}]")


if __name__ == "__main__":
    cli()
