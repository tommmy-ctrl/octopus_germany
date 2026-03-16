"""Shared entity helpers for Octopus Germany entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

CHARGING_DEVICE_TYPES = {"ELECTRIC_VEHICLES", "CHARGE_POINTS"}
WEEKDAY_ORDER = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}


def get_account_device_info(account_number: str) -> DeviceInfo:
    """Get device info for account service."""
    return DeviceInfo(
        identifiers={(DOMAIN, account_number)},
        name=f"Octopus Energy Germany ({account_number})",
        manufacturer="Octopus Energy Germany",
        configuration_url="https://my.octopusenergy.de/",
        entry_type=DeviceEntryType.SERVICE,
    )


def get_device_specific_device_info(
    coordinator_data: dict, account_number: str, device_id: str
) -> DeviceInfo:
    """Get device info for a specific EV-related device."""
    if (
        coordinator_data
        and account_number in coordinator_data
        and "devices" in coordinator_data[account_number]
    ):
        devices = coordinator_data[account_number]["devices"]
        for device in devices:
            if device.get("id") == device_id:
                device_name = device.get("name", f"Device {device_id}")
                device_type = device.get("deviceType", "Unknown Device")
                device_model = device.get("vehicleVariant", {}).get(
                    "model", "Unknown Model"
                )
                device_provider = device.get("provider", "Unknown Provider")

                return DeviceInfo(
                    identifiers={(DOMAIN, f"device_{device_id}")},
                    name=f"{device_name} ({device_type})",
                    manufacturer=device_provider,
                    model=device_model,
                    via_device=(DOMAIN, account_number),
                )

    return DeviceInfo(
        identifiers={(DOMAIN, f"device_{device_id}")},
        name=f"Device ({device_id})",
        manufacturer="Octopus Energy Germany",
        model="Unknown Device",
        via_device=(DOMAIN, account_number),
    )


def normalize_name(value: str) -> str:
    """Normalize names for unique IDs."""
    normalized = value.lower().replace(" ", "_")
    for ch in [
        "/",
        "\\",
        ",",
        ".",
        ":",
        ";",
        "|",
        "[",
        "]",
        "{",
        "}",
        "(",
        ")",
        "'",
        '"',
        "#",
        "?",
        "!",
        "@",
        "=",
        "+",
        "*",
        "%",
        "&",
        "<",
        ">",
    ]:
        normalized = normalized.replace(ch, "_")
    return normalized


def parse_api_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetimes returned by the API."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def extract_device_schedule(device: dict) -> dict[str, Any] | None:
    """Extract the most relevant schedule entry for a charging device."""
    preferences = device.get("preferences", {})
    schedules = preferences.get("schedules", [])
    if not isinstance(schedules, list) or not schedules:
        return None

    today_name = datetime.now().strftime("%A").upper()
    valid_schedules = [schedule for schedule in schedules if isinstance(schedule, dict)]
    if not valid_schedules:
        return None

    today_schedule = next(
        (
            schedule
            for schedule in valid_schedules
            if schedule.get("dayOfWeek") == today_name
        ),
        None,
    )
    if today_schedule:
        return today_schedule

    return min(
        valid_schedules,
        key=lambda schedule: WEEKDAY_ORDER.get(schedule.get("dayOfWeek", ""), 99),
    )


def is_charging_device(device: dict) -> bool:
    """Return whether a device is relevant for EV charging sensors."""
    return device.get("deviceType") in CHARGING_DEVICE_TYPES
