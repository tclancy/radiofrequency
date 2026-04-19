#!/usr/bin/env python3
"""Control RF devices via NodeMCU HTTP API.

    python cli.py send sofa_king_fan bedroom light --host 192.168.1.42
    python cli.py raw 10001100111101101100000000111111 \\
        --device sofa_king_fan --host 192.168.1.42
"""
import sys

import click
import httpx

from src.device import DeviceProfile, build_packet, build_transmit_payload

DEVICES_DIR = "devices"


def _load_profile(device: str) -> DeviceProfile:
    return DeviceProfile.load(f"{DEVICES_DIR}/{device}.yaml")


def _post_transmit(host: str, port: int, payload: dict) -> None:
    url = f"http://{host}:{port}/transmit"
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        click.echo(f"Error: could not connect to {host}:{port}", err=True)
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        click.echo(
            f"Error: NodeMCU returned {exc.response.status_code} — {body}",
            err=True,
        )
        sys.exit(1)


@click.group()
def cli() -> None:
    """Control RF devices via NodeMCU HTTP API."""


@cli.command()
@click.argument("device")
@click.argument("unit")
@click.argument("command")
@click.option("--host", default="nodemcu.local", show_default=True)
@click.option("--port", default=80, show_default=True)
def send(device: str, unit: str, command: str, host: str, port: int) -> None:
    """Send a named command from a device profile (e.g. bedroom light)."""
    profile = _load_profile(device)

    if unit not in profile.units:
        available = ", ".join(sorted(profile.units))
        click.echo(f"Error: unknown unit '{unit}'. Available: {available}", err=True)
        sys.exit(1)

    if command not in profile.commands:
        available = ", ".join(sorted(profile.commands))
        click.echo(f"Error: unknown command '{command}'. Available: {available}", err=True)
        sys.exit(1)

    bits = build_packet(profile, unit=unit, command=command)
    payload = build_transmit_payload(profile, bits=bits)
    _post_transmit(host, port, payload)
    click.echo(f"OK  {command} → {device}/{unit}  [{bits}]")


@cli.command()
@click.argument("bits")
@click.option("--device", required=True, help="Device profile whose timing to use.")
@click.option("--host", default="nodemcu.local", show_default=True)
@click.option("--port", default=80, show_default=True)
def raw(bits: str, device: str, host: str, port: int) -> None:
    """Transmit an arbitrary bit string using a device profile's timing."""
    profile = _load_profile(device)
    try:
        payload = build_transmit_payload(profile, bits=bits)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _post_transmit(host, port, payload)
    click.echo(f"OK  raw [{bits}]  ({len(bits)} bits) via {device}")


if __name__ == "__main__":
    cli()
