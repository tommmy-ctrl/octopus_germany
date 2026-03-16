"""EV and smart charging sensors for Octopus Germany."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil.relativedelta import relativedelta
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity_helpers import (
    get_account_device_info,
    get_device_specific_device_info,
    extract_device_schedule,
    is_charging_device,
    normalize_name,
    parse_api_datetime,
)


def build_ev_entities(account_number: str, coordinator, account_data: dict) -> list:
    """Build EV-related sensors for all charging devices in an account."""
    entities = []
    devices = account_data.get("devices", [])
    charging_sessions = account_data.get("charging_sessions", [])

    for device in devices:
        device_id = device.get("id")
        if not device_id or not is_charging_device(device):
            continue

        entities.extend(
            [
                OctopusNextDispatchStartSensor(account_number, coordinator, device_id),
                OctopusNextDispatchEnergySensor(account_number, coordinator, device_id),
                OctopusLastChargingSessionCostSensor(
                    account_number, coordinator, device_id
                ),
                OctopusLastChargingProblemSensor(account_number, coordinator, device_id),
                OctopusChargingDiagnosticsSensor(account_number, coordinator, device_id),
                OctopusLatestDeviceAlertSensor(account_number, coordinator, device_id),
                OctopusTargetSocSensor(account_number, coordinator, device_id),
                OctopusTargetTimeSensor(account_number, coordinator, device_id),
            ]
        )

        device_name = device.get("name", f"Device_{device_id}")
        device_sessions = [
            session
            for session in charging_sessions
            if session.get("device_id") == device_id
            or session.get("device_name") == device_name
        ]
        entities.append(
            OctopusSmartChargingSessionsSensor(
                account_number,
                coordinator,
                device_name,
                device_id,
                device_sessions,
            )
        )

    return entities


class OctopusChargingDeviceSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for a specific charging-capable device."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._device_id = device_id

        device = self._get_device_data()
        self._device_name = (
            device.get("name", f"Device_{device_id}")
            if device
            else f"Device_{device_id}"
        )
        self._norm_name = normalize_name(self._device_name)
        self._attr_has_entity_name = False

    def _get_account_data(self) -> dict:
        """Return account data from the coordinator."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return {}
        return self.coordinator.data[self._account_number]

    def _get_device_data(self) -> dict | None:
        """Return device data for the configured device ID."""
        account_data = self._get_account_data()
        for device in account_data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    def _get_device_sessions(self) -> list[dict]:
        """Return charging sessions for the configured device."""
        account_data = self._get_account_data()
        sessions = account_data.get("charging_sessions") or []
        return [
            session
            for session in sessions
            if session.get("device_id") == self._device_id
            or session.get("device_name") == self._device_name
        ]

    def _get_device_alerts(self) -> list[dict]:
        """Return device alerts sorted with newest first."""
        device = self._get_device_data() or {}
        alerts = device.get("alerts") or []
        valid_alerts = [alert for alert in alerts if isinstance(alert, dict)]
        return sorted(
            valid_alerts,
            key=lambda alert: parse_api_datetime(alert.get("publishedAt"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def _get_device_status(self) -> dict[str, Any]:
        """Return the current device status payload."""
        device = self._get_device_data() or {}
        status = device.get("status") or {}
        return status if isinstance(status, dict) else {}

    def _get_last_session(self) -> dict | None:
        """Return the most recent charging session for this device."""
        sessions_with_start = [
            session
            for session in self._get_device_sessions()
            if parse_api_datetime(session.get("start")) is not None
        ]
        if not sessions_with_start:
            return None

        return max(
            sessions_with_start,
            key=lambda session: parse_api_datetime(session.get("start"))
            or datetime.min.replace(tzinfo=timezone.utc),
        )

    def _get_next_dispatch(self) -> dict | None:
        """Return the next planned dispatch for this device."""
        account_data = self._get_account_data()
        dispatches = account_data.get("planned_dispatches") or account_data.get(
            "plannedDispatches", []
        )
        now = datetime.now(timezone.utc)

        next_dispatch = None
        next_start = None
        for dispatch in dispatches:
            dispatch_device_id = dispatch.get("deviceId") or dispatch.get(
                "meta", {}
            ).get("deviceId")
            if dispatch_device_id != self._device_id:
                continue

            start = parse_api_datetime(dispatch.get("start"))
            if start is None or start < now:
                continue

            if next_start is None or start < next_start:
                next_dispatch = dispatch
                next_start = start

        return next_dispatch

    def _get_target_schedule(self) -> dict[str, Any] | None:
        """Return the relevant recurring target schedule for the device."""
        device = self._get_device_data()
        if not device:
            return None
        return extract_device_schedule(device)

    def _get_last_problem_details(self) -> dict[str, Any] | None:
        """Return the most relevant problem details of the latest charging session."""
        session = self._get_last_session()
        if not session:
            return None

        if session.get("has_error"):
            return {
                "problem_type": "error",
                "problem_value": session.get("error_cause"),
                "session": session,
            }

        if session.get("has_truncation"):
            return {
                "problem_type": "truncation",
                "problem_value": session.get("truncation_cause"),
                "session": session,
            }

        return {
            "problem_type": "none",
            "problem_value": "none",
            "session": session,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self._get_device_data() is not None
        )

    @property
    def device_info(self):
        """Return device information."""
        return get_device_specific_device_info(
            self.coordinator.data, self._account_number, self._device_id
        )


class OctopusNextDispatchStartSensor(OctopusChargingDeviceSensor):
    """Sensor for the next planned dispatch start time."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the next dispatch start sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Next Dispatch Start"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_next_dispatch_start"
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:clock-start"

    @property
    def native_value(self) -> datetime | None:
        """Return the next dispatch start time."""
        dispatch = self._get_next_dispatch()
        return parse_api_datetime(dispatch.get("start")) if dispatch else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        dispatch = self._get_next_dispatch()
        if not dispatch:
            return {
                "device_id": self._device_id,
                "device_name": self._device_name,
                "account_number": self._account_number,
            }

        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "end": dispatch.get("end"),
            "energy_kwh": dispatch.get("deltaKwh"),
            "dispatch_type": dispatch.get("type"),
        }


class OctopusNextDispatchEnergySensor(OctopusChargingDeviceSensor):
    """Sensor for the energy of the next planned dispatch."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the next dispatch energy sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Next Dispatch Energy"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_next_dispatch_energy"
        )
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:transmission-tower-export"

    @property
    def native_value(self) -> float | None:
        """Return the planned energy of the next dispatch in kWh."""
        dispatch = self._get_next_dispatch()
        if not dispatch:
            return None

        try:
            delta_kwh = dispatch.get("deltaKwh", dispatch.get("delta"))
            return float(delta_kwh) if delta_kwh is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        dispatch = self._get_next_dispatch()
        if not dispatch:
            return {
                "device_id": self._device_id,
                "device_name": self._device_name,
                "account_number": self._account_number,
            }

        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "start": dispatch.get("start"),
            "end": dispatch.get("end"),
            "dispatch_type": dispatch.get("type"),
        }


class OctopusLastChargingSessionCostSensor(OctopusChargingDeviceSensor):
    """Sensor for the cost of the last charging session."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the last session cost sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Last Charging Cost"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_last_charging_cost"
        )
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:cash"

    @property
    def native_value(self) -> float | None:
        """Return the cost of the most recent charging session."""
        session = self._get_last_session()
        if not session:
            return None

        try:
            amount = (session.get("cost") or {}).get("amount")
            return float(amount) if amount is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        session = self._get_last_session()
        if not session:
            return {
                "device_id": self._device_id,
                "device_name": self._device_name,
                "account_number": self._account_number,
                "sessions_available": len(self._get_device_sessions()),
            }

        energy = session.get("energyAdded") or {}
        cost = session.get("cost") or {}
        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "session_start": session.get("start"),
            "session_end": session.get("end"),
            "session_type": session.get("type"),
            "energy_kwh": energy.get("value"),
            "energy_unit": energy.get("unit"),
            "soc_change": session.get("state_of_charge_change"),
            "soc_final": session.get("state_of_charge_final"),
            "target_type": session.get("targetType"),
            "dispatches_utilized": session.get("dispatches_utilized"),
            "error_cause": session.get("error_cause"),
            "truncation_cause": session.get("truncation_cause"),
            "cost_currency": cost.get("currency", "EUR"),
        }


class OctopusLastChargingProblemSensor(OctopusChargingDeviceSensor):
    """Sensor for the most recent charging problem cause."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the last charging problem sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Last Charging Problem"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_last_charging_problem"
        )
        self._attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        """Return the latest charging problem or 'none'."""
        details = self._get_last_problem_details()
        if not details:
            return None
        return details.get("problem_value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        details = self._get_last_problem_details()
        if not details:
            return {
                "device_id": self._device_id,
                "device_name": self._device_name,
                "account_number": self._account_number,
            }

        session = details.get("session") or {}
        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "problem_type": details.get("problem_type"),
            "session_start": session.get("start"),
            "session_end": session.get("end"),
            "session_type": session.get("type"),
            "soc_final": session.get("state_of_charge_final"),
            "achievable_soc": session.get("achievable_soc"),
            "original_achievable_soc": session.get("original_achievable_soc"),
            "dispatches_utilized": session.get("dispatches_utilized"),
        }


class OctopusChargingDiagnosticsSensor(OctopusChargingDeviceSensor):
    """Combined diagnostic sensor for smart charging state and issues."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the charging diagnostics sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Charging Diagnostics"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_charging_diagnostics"
        )
        self._attr_icon = "mdi:car-electric"

    @property
    def native_value(self) -> str | None:
        """Return the most relevant current diagnostic state."""
        status = self._get_device_status()
        details = self._get_last_problem_details()
        alerts = self._get_device_alerts()

        if details and details.get("problem_type") == "error":
            return f"error:{details.get('problem_value')}"
        if details and details.get("problem_type") == "truncation":
            return f"truncation:{details.get('problem_value')}"
        if alerts:
            return "alert_active"
        if status.get("isSuspended"):
            return "suspended"

        current_state = status.get("currentState")
        if current_state:
            return str(current_state).lower()

        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return combined diagnostics as attributes."""
        device = self._get_device_data() or {}
        status = self._get_device_status()
        details = self._get_last_problem_details() or {}
        session = details.get("session") or self._get_last_session() or {}
        next_dispatch = self._get_next_dispatch() or {}
        alerts = self._get_device_alerts()
        latest_alert = alerts[0] if alerts else {}
        schedule = self._get_target_schedule()
        preferences = device.get("preferences", {})

        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "provider": device.get("provider"),
            "device_type": device.get("deviceType"),
            "current_status": status.get("current"),
            "current_state": status.get("currentState"),
            "is_suspended": status.get("isSuspended"),
            "test_dispatch_failure_reason": status.get("testDispatchFailureReason"),
            "soc_limit_upper": (status.get("stateOfChargeLimit") or {}).get(
                "upperSocLimit"
            ),
            "soc_limit_timestamp": (status.get("stateOfChargeLimit") or {}).get(
                "timestamp"
            ),
            "soc_limit_violated": (status.get("stateOfChargeLimit") or {}).get(
                "isLimitViolated"
            ),
            "latest_problem_type": details.get("problem_type"),
            "latest_problem_value": details.get("problem_value"),
            "latest_alert_message": latest_alert.get("message"),
            "latest_alert_published_at": latest_alert.get("publishedAt"),
            "alerts_count": len(alerts),
            "last_session_start": session.get("start"),
            "last_session_end": session.get("end"),
            "last_session_type": session.get("type"),
            "last_session_energy_kwh": (session.get("energyAdded") or {}).get(
                "value"
            ),
            "last_session_cost_eur": (session.get("cost") or {}).get("amount"),
            "last_session_soc_final": session.get("state_of_charge_final"),
            "last_session_soc_change": session.get("state_of_charge_change"),
            "dispatches_utilized": session.get("dispatches_utilized"),
            "error_cause": session.get("error_cause"),
            "truncation_cause": session.get("truncation_cause"),
            "achievable_soc": session.get("achievable_soc"),
            "original_achievable_soc": session.get("original_achievable_soc"),
            "next_dispatch_start": next_dispatch.get("start"),
            "next_dispatch_end": next_dispatch.get("end"),
            "next_dispatch_type": next_dispatch.get("type"),
            "next_dispatch_energy_kwh": next_dispatch.get("deltaKwh"),
            "target_soc": schedule.get("max") if schedule else None,
            "target_min_soc": schedule.get("min") if schedule else None,
            "target_time": schedule.get("time") if schedule else None,
            "target_day": schedule.get("dayOfWeek") if schedule else None,
            "target_type": preferences.get("targetType"),
            "preference_mode": preferences.get("mode"),
            "preference_unit": preferences.get("unit"),
            "grid_export": preferences.get("gridExport"),
        }


class OctopusLatestDeviceAlertSensor(OctopusChargingDeviceSensor):
    """Sensor for the latest active device alert."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the latest device alert sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Latest Device Alert"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_latest_device_alert"
        )
        self._attr_icon = "mdi:message-alert-outline"

    @property
    def native_value(self) -> str | None:
        """Return the latest device alert message."""
        alerts = self._get_device_alerts()
        if not alerts:
            return None
        return alerts[0].get("message")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        alerts = self._get_device_alerts()
        latest_alert = alerts[0] if alerts else {}
        return {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "alerts_count": len(alerts),
            "published_at": latest_alert.get("publishedAt"),
            "all_alerts": alerts,
        }


class OctopusTargetSocSensor(OctopusChargingDeviceSensor):
    """Sensor for the configured target state of charge."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the target SOC sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = f"Octopus {account_number} {self._device_name} Target SOC"
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_target_soc"
        )
        self._attr_native_unit_of_measurement = "%"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-lock"

    @property
    def native_value(self) -> int | None:
        """Return the configured target SOC."""
        schedule = self._get_target_schedule()
        if not schedule:
            return None

        try:
            max_value = schedule.get("max")
            return int(max_value) if max_value is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        device = self._get_device_data() or {}
        schedule = self._get_target_schedule()
        preferences = device.get("preferences", {})

        attributes = {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "mode": preferences.get("mode"),
            "target_type": preferences.get("targetType"),
            "unit": preferences.get("unit"),
        }
        if schedule:
            attributes.update(
                {
                    "schedule_day": schedule.get("dayOfWeek"),
                    "target_time": schedule.get("time"),
                    "target_min_soc": schedule.get("min"),
                }
            )
        return attributes


class OctopusTargetTimeSensor(OctopusChargingDeviceSensor):
    """Sensor for the configured target time."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the target time sensor."""
        super().__init__(account_number, coordinator, device_id)
        self._attr_name = (
            f"Octopus {account_number} {self._device_name} Target Time"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{self._norm_name}_target_time"
        )
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str | None:
        """Return the configured target time."""
        schedule = self._get_target_schedule()
        if not schedule:
            return None
        return schedule.get("time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        device = self._get_device_data() or {}
        schedule = self._get_target_schedule()
        preferences = device.get("preferences", {})

        attributes = {
            "device_id": self._device_id,
            "device_name": self._device_name,
            "account_number": self._account_number,
            "mode": preferences.get("mode"),
            "target_type": preferences.get("targetType"),
            "unit": preferences.get("unit"),
            "grid_export": preferences.get("gridExport"),
        }
        if schedule:
            attributes.update(
                {
                    "schedule_day": schedule.get("dayOfWeek"),
                    "target_soc": schedule.get("max"),
                    "target_min_soc": schedule.get("min"),
                }
            )
        return attributes


class OctopusSmartChargingSessionsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for smart charging sessions of a specific EV device."""

    def __init__(
        self, account_number, coordinator, device_name, device_id, sessions
    ) -> None:
        """Initialize the smart charging sessions sensor for a specific device."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._device_name = device_name
        self._device_id = device_id
        norm_name = normalize_name(device_name)
        self._attr_name = (
            f"Octopus {account_number} {device_name} Smart Charging Sessions"
        )
        self._attr_unique_id = (
            f"octopus_{account_number}_{norm_name}_smart_charging_sessions"
        )
        self._attr_icon = "mdi:ev-station"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_has_entity_name = False

        self._sessions = sessions or []
        self._cached_value = 0
        self._cached_attributes = {}

    @property
    def native_value(self) -> int:
        """Return the count of smart charging sessions in the current month."""
        current_month = datetime.now().strftime("%Y-%m")
        smart_sessions_sorted = sorted(
            self._sessions,
            key=lambda session: session.get("start") or "",
            reverse=True,
        )
        smart_sessions_current_month = []

        for session in smart_sessions_sorted:
            start_dt = parse_api_datetime(session.get("start"))
            energy = session.get("energyAdded", {}) or {}
            energy_kwh = float(energy.get("value", 0) or 0)
            if energy_kwh == 0.0:
                continue

            if start_dt and start_dt.strftime("%Y-%m") == current_month:
                smart_sessions_current_month.append(session)

        return len(smart_sessions_current_month)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes for the smart charging sessions sensor."""
        if self._cached_attributes:
            return self._cached_attributes

        current_month = datetime.now().strftime("%Y-%m")
        smart_sessions_sorted = sorted(
            self._sessions,
            key=lambda session: session.get("start") or "",
            reverse=True,
        )
        now = datetime.now(timezone.utc)
        min_date = now - relativedelta(years=2)
        sessions_list = []
        sessions_by_month = {}
        total_energy = 0.0

        for session in smart_sessions_sorted:
            start_dt = parse_api_datetime(session.get("start"))
            if start_dt and start_dt < min_date:
                continue

            energy = session.get("energyAdded", {}) or {}
            energy_kwh = float(energy.get("value", 0) or 0)
            if energy_kwh == 0.0:
                continue

            cost = session.get("cost") or {}
            sessions_list.append(
                {
                    "start": session.get("start"),
                    "end": session.get("end"),
                    "energy_kwh": energy_kwh,
                    "cost_eur": cost.get("amount", 0) if cost else 0,
                    "device_name": session.get("device_name", "Unknown"),
                    "type": session.get("type", "UNKNOWN"),
                    "is_successful": session.get("is_successful", True),
                    "has_error": session.get("has_error", False),
                    "has_truncation": session.get("has_truncation", False),
                    "has_ended": session.get("has_ended", True),
                    "has_energy": session.get("has_energy", False),
                    "dispatches_utilized": session.get("dispatches_utilized", True),
                    "soc_final": session.get("soc_final"),
                    "error_cause": session.get("error_cause"),
                    "truncation_cause": session.get("truncation_cause"),
                }
            )
            if start_dt:
                month_key = start_dt.strftime("%Y-%m")
                sessions_by_month.setdefault(month_key, []).append(session)
            total_energy += energy_kwh

        qualified_month_list = []
        if sessions_list:
            session_months = [
                parse_api_datetime(session["start"]).strftime("%Y-%m")
                for session in sessions_list
                if session.get("start") and parse_api_datetime(session["start"])
            ]
            if session_months:
                current = datetime.strptime(min(session_months), "%Y-%m")
                end = datetime.strptime(max(session_months), "%Y-%m")
                months = []
                while current <= end:
                    months.append(current.strftime("%Y-%m"))
                    current += relativedelta(months=1)
                qualified_month_list = [
                    month
                    for month in months
                    if month in sessions_by_month and len(sessions_by_month[month]) >= 5
                ]

        current_month_count = len(sessions_by_month.get(current_month, []))
        attributes = {
            "smart_sessions_count": len(sessions_list),
            "total_energy_kwh": round(total_energy, 2),
            "qualified_months": len(qualified_month_list),
            "qualified_month_list": qualified_month_list,
            "current_month": current_month,
            "current_month_count": current_month_count,
            "current_month_qualified": current_month_count >= 5,
            "recent_sessions": sessions_list,
        }
        self._cached_attributes = attributes
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
        )

    @property
    def device_info(self):
        """Return device information."""
        return get_account_device_info(self._account_number)
