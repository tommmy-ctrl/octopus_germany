"""Shared normalization helpers for account and dispatch data."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import as_utc, parse_datetime, utcnow

from ..const import DOMAIN


def initialize_account_result(account_number: str) -> dict[str, dict[str, Any]]:
    """Initialize the normalized result structure for a single account."""
    return {
        account_number: {
            "account_number": account_number,
            "electricity_balance": 0,
            "planned_dispatches": [],
            "completed_dispatches": [],
            "property_ids": [],
            "devices": [],
            "products": [],
            "gas_products": [],
            "vehicle_battery_size_in_kwh": None,
            "current_start": None,
            "current_end": None,
            "next_start": None,
            "next_end": None,
            "ledgers": [],
            "malo_number": None,
            "melo_number": None,
            "meter": None,
            "gas_malo_number": None,
            "gas_melo_number": None,
            "gas_meter": None,
        }
    }


def get_cached_account_data(
    hass: HomeAssistant, entry: ConfigEntry, account_number: str
) -> dict[str, Any]:
    """Return the cached account data from the coordinator if available."""
    try:
        cached_coordinator = (
            hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
        )
        if cached_coordinator and cached_coordinator.data:
            return cached_coordinator.data.get(account_number, {}) or {}
    except Exception:
        return {}

    return {}


def extract_vehicle_battery_size(devices: list[dict[str, Any]]) -> float | None:
    """Extract the first available vehicle battery size from device data."""
    for device in devices:
        if device.get("vehicleVariant") and device["vehicleVariant"].get("batterySize"):
            try:
                return float(device["vehicleVariant"]["batterySize"])
            except (ValueError, TypeError):
                continue
    return None


def calculate_dispatch_windows(
    planned_dispatches: list[dict[str, Any]], logger: logging.Logger
) -> tuple[Any, Any, Any, Any]:
    """Calculate current and next dispatch windows from planned dispatches."""
    now = utcnow()
    current_start = None
    current_end = None
    next_start = None
    next_end = None

    for dispatch in sorted(planned_dispatches, key=lambda x: x.get("start", "")):
        try:
            start_str = dispatch.get("start")
            end_str = dispatch.get("end")

            if not start_str or not end_str:
                continue

            start = as_utc(parse_datetime(start_str))
            end = as_utc(parse_datetime(end_str))

            if start <= now <= end:
                current_start = start
                current_end = end
            elif now < start and not next_start:
                next_start = start
                next_end = end
        except (ValueError, TypeError) as err:
            logger.error("Error parsing dispatch dates: %s - %s", dispatch, str(err))

    return current_start, current_end, next_start, next_end


def is_currently_valid_product(product: dict[str, Any], now_iso: str) -> bool:
    """Return whether a product is valid at the provided ISO timestamp."""
    valid_from = product.get("validFrom")
    valid_to = product.get("validTo")

    if not valid_from:
        return False

    return valid_from <= now_iso and (not valid_to or now_iso <= valid_to)


def calculate_days_until_iso_datetime(date_value: str) -> int | None:
    """Return days until an ISO datetime string, clamped at zero."""
    try:
        end_date = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        now_date = datetime.now(end_date.tzinfo)
        return max(0, (end_date - now_date).days)
    except (ValueError, TypeError):
        return None
