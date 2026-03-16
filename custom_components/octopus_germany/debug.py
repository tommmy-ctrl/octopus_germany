"""Shared debug helpers for the Octopus Germany integration."""

from __future__ import annotations

import logging
from typing import Any


def log_debug_mode_info(
    logger: logging.Logger, enabled: bool, message: str, *args: Any
) -> None:
    """Emit concise debug-mode logs that stay readable at info level."""
    if enabled:
        logger.info("Debug mode: " + message, *args)


def format_debug_datetime(value: Any) -> str:
    """Format datetime-like values for compact debug logs."""
    if value is None:
        return "none"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def log_account_debug_summary(
    logger: logging.Logger,
    enabled: bool,
    account_number: str,
    account_data: dict[str, Any],
    fallbacks_used: list[str],
) -> None:
    """Log a compact per-account summary for troubleshooting."""
    if not enabled:
        return

    devices = account_data.get("devices") or []
    planned_dispatches = account_data.get("planned_dispatches") or []
    completed_dispatches = account_data.get("completed_dispatches") or []
    charging_sessions = account_data.get("charging_sessions") or []
    smart_meter_readings = account_data.get("electricity_smart_meter_readings") or []
    products = account_data.get("products") or []
    gas_products = account_data.get("gas_products") or []

    log_debug_mode_info(
        logger,
        True,
        "Account %s summary: devices=%d planned_dispatches=%d completed_dispatches=%d sessions=%d products=%d gas_products=%d smart_meter_readings=%d current_dispatch=%s->%s next_dispatch=%s->%s fallbacks=%s",
        account_number,
        len(devices),
        len(planned_dispatches),
        len(completed_dispatches),
        len(charging_sessions),
        len(products),
        len(gas_products),
        len(smart_meter_readings),
        format_debug_datetime(account_data.get("current_start")),
        format_debug_datetime(account_data.get("current_end")),
        format_debug_datetime(account_data.get("next_start")),
        format_debug_datetime(account_data.get("next_end")),
        ", ".join(fallbacks_used) if fallbacks_used else "none",
    )

    sessions_by_device: dict[str, list[dict[str, Any]]] = {}
    for session in charging_sessions:
        device_id = session.get("device_id")
        if not device_id:
            continue
        sessions_by_device.setdefault(device_id, []).append(session)

    for device in devices:
        device_id = device.get("id")
        status = device.get("status", {}) or {}
        alerts = device.get("alerts", []) or []
        device_sessions = sessions_by_device.get(device_id, [])
        latest_session = None
        if device_sessions:
            latest_session = max(device_sessions, key=lambda s: s.get("start") or "")

        latest_problem = "none"
        if latest_session:
            if latest_session.get("error_cause"):
                latest_problem = f"error:{latest_session.get('error_cause')}"
            elif latest_session.get("truncation_cause"):
                latest_problem = f"truncation:{latest_session.get('truncation_cause')}"

        device_dispatches = [
            dispatch
            for dispatch in planned_dispatches
            if dispatch.get("deviceId") == device_id
            or (dispatch.get("meta", {}) or {}).get("deviceId") == device_id
        ]

        log_debug_mode_info(
            logger,
            True,
            "Device %s (%s/%s): current=%s state=%s suspended=%s alerts=%d sessions=%d latest_problem=%s planned_dispatches=%d",
            device.get("name", device_id or "unknown"),
            device.get("deviceType", "unknown"),
            device.get("provider", "unknown"),
            status.get("current"),
            status.get("currentState"),
            status.get("isSuspended"),
            len(alerts),
            len(device_sessions),
            latest_problem,
            len(device_dispatches),
        )


def log_graphql_response_summary(
    logger: logging.Logger,
    enabled: bool,
    operation: str,
    account_number: str,
    response: dict[str, Any] | None,
) -> None:
    """Log a compact GraphQL response summary for easier troubleshooting."""
    if not enabled:
        return

    if not isinstance(response, dict):
        log_debug_mode_info(
            logger,
            True,
            "%s for %s returned non-dict response: %s",
            operation,
            account_number,
            type(response).__name__,
        )
        return

    data = response.get("data")
    data_keys = sorted(data.keys()) if isinstance(data, dict) else []
    errors = response.get("errors") or []

    log_debug_mode_info(
        logger,
        True,
        "%s response for %s: data_keys=%s errors=%d",
        operation,
        account_number,
        data_keys,
        len(errors),
    )

    for error in errors[:5]:
        path = ".".join(str(part) for part in error.get("path", [])) or "n/a"
        code = error.get("extensions", {}).get("errorCode", "unknown")
        message = error.get("message", "Unknown error")
        log_debug_mode_info(
            logger,
            True,
            "%s GraphQL error for %s: code=%s path=%s message=%s",
            operation,
            account_number,
            code,
            path,
            message,
        )

    if len(errors) > 5:
        log_debug_mode_info(
            logger,
            True,
            "%s for %s has %d additional GraphQL errors not shown",
            operation,
            account_number,
            len(errors) - 5,
        )
