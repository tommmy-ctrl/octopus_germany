"""Meter, reading, contract, and device sensors for Octopus Germany."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity_helpers import get_account_device_info

_LOGGER = logging.getLogger(__name__)


def build_meter_entities(account_number: str, coordinator, account_data: dict) -> list:
    """Build meter-, reading-, contract-, and device-related entities."""
    entities = []

    if account_data.get("malo_number"):
        if account_data.get("electricity_latest_reading"):
            entities.append(
                OctopusElectricityLatestReadingSensor(account_number, coordinator)
            )
        entities.append(
            OctopusElectricitySmartMeterReadingsSensor(account_number, coordinator)
        )

    if account_data.get("gas_malo_number"):
        entities.append(OctopusGasMaloSensor(account_number, coordinator))

        if account_data.get("gas_melo_number"):
            entities.append(OctopusGasMeloSensor(account_number, coordinator))

        if account_data.get("gas_meter"):
            entities.append(OctopusGasMeterSensor(account_number, coordinator))

        if account_data.get("gas_latest_reading"):
            entities.append(OctopusGasLatestReadingSensor(account_number, coordinator))

        if account_data.get("gas_price") is not None:
            entities.append(OctopusGasPriceSensor(account_number, coordinator))

        if account_data.get("gas_meter_smart_reading") is not None:
            entities.append(OctopusGasSmartReadingSensor(account_number, coordinator))

        if account_data.get("gas_contract_start"):
            entities.append(OctopusGasContractStartSensor(account_number, coordinator))

        if account_data.get("gas_contract_end"):
            entities.append(OctopusGasContractEndSensor(account_number, coordinator))

        if account_data.get("gas_contract_days_until_expiry") is not None:
            entities.append(
                OctopusGasContractExpiryDaysSensor(account_number, coordinator)
            )

    for device in account_data.get("devices", []):
        device_id = device.get("id")
        if device_id:
            entities.append(
                OctopusDeviceStatusSensor(account_number, coordinator, device_id)
            )

    return entities

class OctopusGasMaloSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas MALO number."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas MALO sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas MALO Number"
        self._attr_unique_id = f"octopus_{account_number}_gas_malo_number"
        self._attr_has_entity_name = False
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the gas MALO number."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("gas_malo_number")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_malo_number")
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasMeloSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas MELO number."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas MELO sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas MELO Number"
        self._attr_unique_id = f"octopus_{account_number}_gas_melo_number"
        self._attr_has_entity_name = False
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        """Return the gas MELO number."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("gas_melo_number")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_melo_number")
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasMeterSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas meter information."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas meter sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Meter"
        self._attr_unique_id = f"octopus_{account_number}_gas_meter"
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    @property
    def native_value(self) -> str | None:
        """Return the gas meter number."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        gas_meter = account_data.get("gas_meter", {})

        if gas_meter and isinstance(gas_meter, dict):
            return gas_meter.get("number", None)

        return None

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        default_attributes = {
            "meter_id": "Unknown",
            "meter_number": "Unknown",
            "meter_type": "Unknown",
            "account_number": self._account_number,
        }

        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            self._attributes = default_attributes
            return

        account_data = self.coordinator.data[self._account_number]
        gas_meter = account_data.get("gas_meter", {})

        if gas_meter and isinstance(gas_meter, dict):
            self._attributes = {
                "meter_id": gas_meter.get("id", "Unknown"),
                "meter_number": gas_meter.get("number", "Unknown"),
                "meter_type": gas_meter.get("meterType", "Unknown"),
                "account_number": self._account_number,
            }
        else:
            self._attributes = default_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        self._update_attributes()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_meter") is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasLatestReadingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany latest gas meter reading."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas latest reading sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Latest Reading"
        self._attr_unique_id = f"octopus_{account_number}_gas_latest_reading"
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    @property
    def native_value(self) -> float | None:
        """Return the latest gas meter reading value."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        gas_reading = account_data.get("gas_latest_reading")

        if gas_reading and isinstance(gas_reading, dict):
            try:
                reading_value = gas_reading.get("value")
                if reading_value is not None:
                    return float(reading_value)
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid gas meter reading value: %s", reading_value)

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        # Since the GraphQL API doesn't provide units directly for gas readings,
        # we default to mÂ³ which is the standard for gas consumption in Germany
        return "mÂ³"

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        default_attributes = {
            "reading_value": "Unknown",
            "reading_units": "mÂ³",
            "reading_date": "Unknown",
            "reading_origin": "Unknown",
            "reading_type": "Unknown",
            "register_obis_code": "Unknown",
            "meter_id": "Unknown",
            "account_number": self._account_number,
        }

        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            self._attributes = default_attributes
            return

        account_data = self.coordinator.data[self._account_number]
        gas_reading = account_data.get("gas_latest_reading")

        if gas_reading and isinstance(gas_reading, dict):
            # Extract reading date from readAt
            reading_date = gas_reading.get("readAt")

            # Format the date if available
            if reading_date:
                try:
                    # Try to parse and format the date
                    parsed_date = datetime.fromisoformat(
                        reading_date.replace("Z", "+00:00")
                    )
                    reading_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    # Keep original date if parsing fails
                    pass

            self._attributes = {
                "reading_value": gas_reading.get("value", "Unknown"),
                "reading_units": "mÂ³",
                "reading_date": reading_date or "Unknown",
                "reading_origin": gas_reading.get("origin", "Unknown"),
                "reading_type": gas_reading.get("typeOfRead", "Unknown"),
                "register_obis_code": gas_reading.get("registerObisCode", "Unknown"),
                "meter_id": gas_reading.get("meterId", "Unknown"),
                "read_at": gas_reading.get("readAt", "Unknown"),
                "account_number": self._account_number,
            }
        else:
            self._attributes = default_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        self._update_attributes()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_latest_reading")
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusElectricityLatestReadingSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany latest electricity meter reading."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the electricity latest reading sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Electricity Latest Reading"
        self._attr_unique_id = f"octopus_{account_number}_electricity_latest_reading"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    @property
    def native_value(self) -> float | None:
        """Return the latest electricity meter reading value."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        electricity_reading = account_data.get("electricity_latest_reading")

        if electricity_reading and isinstance(electricity_reading, dict):
            try:
                reading_value = electricity_reading.get("value")
                if reading_value is not None:
                    return float(reading_value)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Invalid electricity meter reading value: %s", reading_value
                )

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        # Default to kWh which is the standard for electricity consumption in Germany
        return "kWh"

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        default_attributes = {
            "reading_value": "Unknown",
            "reading_units": "kWh",
            "reading_date": "Unknown",
            "reading_origin": "Unknown",
            "reading_type": "Unknown",
            "register_obis_code": "Unknown",
            "register_type": "Unknown",
            "meter_id": "Unknown",
            "account_number": self._account_number,
        }

        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            self._attributes = default_attributes
            return

        account_data = self.coordinator.data[self._account_number]
        electricity_reading = account_data.get("electricity_latest_reading")

        if electricity_reading and isinstance(electricity_reading, dict):
            # Extract reading date from readAt
            reading_date = electricity_reading.get("readAt")

            # Format the date if available
            if reading_date:
                try:
                    # Try to parse and format the date
                    parsed_date = datetime.fromisoformat(
                        reading_date.replace("Z", "+00:00")
                    )
                    reading_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    # Keep original date if parsing fails
                    pass

            self._attributes = {
                "reading_value": electricity_reading.get("value", "Unknown"),
                "reading_units": "kWh",
                "reading_date": reading_date or "Unknown",
                "reading_origin": electricity_reading.get("origin", "Unknown"),
                "reading_type": electricity_reading.get("typeOfRead", "Unknown"),
                "register_obis_code": electricity_reading.get(
                    "registerObisCode", "Unknown"
                ),
                "register_type": electricity_reading.get("registerType", "Unknown"),
                "meter_id": electricity_reading.get("meterId", "Unknown"),
                "read_at": electricity_reading.get("readAt", "Unknown"),
                "account_number": self._account_number,
            }
        else:
            self._attributes = default_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        self._update_attributes()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get(
                "electricity_latest_reading"
            )
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas price."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas price sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Price"
        self._attr_unique_id = f"octopus_{account_number}_gas_price"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "â‚¬/kWh"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> float:
        """Return the gas price."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("gas_price")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_price") is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasSmartReadingSensor(CoordinatorEntity, SensorEntity):
    """Binary sensor for Octopus Germany gas meter smart reading capability."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas smart reading sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Smart Reading"
        self._attr_unique_id = f"octopus_{account_number}_gas_smart_reading"
        self._attr_has_entity_name = False
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return whether smart reading is enabled."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return "Unknown"

        account_data = self.coordinator.data[self._account_number]
        smart_reading = account_data.get("gas_meter_smart_reading")

        if smart_reading is None:
            return "Unknown"
        elif smart_reading:
            return "Enabled"
        else:
            return "Disabled"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get(
                "gas_meter_smart_reading"
            )
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasContractStartSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas contract start date."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas contract start sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Contract Start"
        self._attr_unique_id = f"octopus_{account_number}_gas_contract_start"
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_has_entity_name = False
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        """Return the gas contract start date."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        contract_start = account_data.get("gas_contract_start")

        if contract_start:
            try:
                # Parse ISO date and return date object for DATE device class
                from datetime import datetime

                parsed_date = datetime.fromisoformat(
                    contract_start.replace("Z", "+00:00")
                )
                return parsed_date.date()
            except (ValueError, TypeError):
                return None

        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_contract_start")
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasContractEndSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas contract end date."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas contract end sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Contract End"
        self._attr_unique_id = f"octopus_{account_number}_gas_contract_end"
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_has_entity_name = False
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        """Return the gas contract end date."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        contract_end = account_data.get("gas_contract_end")

        if contract_end:
            try:
                # Parse ISO date and return date object for DATE device class
                from datetime import datetime

                parsed_date = datetime.fromisoformat(
                    contract_end.replace("Z", "+00:00")
                )
                return parsed_date.date()
            except (ValueError, TypeError):
                return None

        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get("gas_contract_end")
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasContractExpiryDaysSensor(CoordinatorEntity, SensorEntity):
    """Sensor for days until Octopus Germany gas contract expiry."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas contract expiry days sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Contract Days Until Expiry"
        self._attr_unique_id = f"octopus_{account_number}_gas_contract_expiry_days"
        self._attr_native_unit_of_measurement = "days"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> int:
        """Return the days until gas contract expiry."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("gas_contract_days_until_expiry")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
            and self.coordinator.data[self._account_number].get(
                "gas_contract_days_until_expiry"
            )
            is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusDeviceStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany device status."""

    def __init__(self, account_number, coordinator, device_id: str) -> None:
        """Initialize the device status sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._device_id = device_id
        # Device name ermitteln
        device_name = None
        if (
            coordinator.data
            and isinstance(coordinator.data, dict)
            and account_number in coordinator.data
        ):
            account_data = coordinator.data[account_number]
            devices = account_data.get("devices", [])
            for device in devices:
                if device.get("id") == device_id:
                    device_name = device.get("name", f"Device_{device_id}")
                    break
        if not device_name:
            device_name = f"Device_{device_id}"
        norm_name = device_name.lower().replace(" ", "_")
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
            norm_name = norm_name.replace(ch, "_")
        self._attr_name = f"Octopus {account_number} {device_name} Status"
        self._attr_unique_id = f"octopus_{account_number}_{norm_name}_status"
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    def _get_device_data(self) -> dict | None:
        """Get device data for this specific device_id."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        devices = account_data.get("devices", [])

        for device in devices:
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def native_value(self) -> str | None:
        """Return the current device status."""
        device = self._get_device_data()
        if device:
            status = device.get("status", {})
            return status.get("currentState", "Unknown")
        return None

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        default_attributes = {
            "device_id": "Unknown",
            "device_name": "Unknown",
            "device_model": "Unknown",
            "device_provider": "Unknown",
            "account_number": self._account_number,
        }

        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            self._attributes = default_attributes
            return

        account_data = self.coordinator.data[self._account_number]
        devices = account_data.get("devices", [])

        if not devices:
            self._attributes = default_attributes
            return

        device = self._get_device_data()
        if not device:
            self._attributes = default_attributes
            return

        self._attributes = {
            "device_id": device.get("id", "Unknown"),
            "device_name": device.get("name", "Unknown"),
            "device_model": device.get("vehicleVariant", {}).get("model", "Unknown"),
            "device_provider": device.get("provider", "Unknown"),
            "battery_size": device.get("vehicleVariant", {}).get(
                "batterySize", "Unknown"
            ),
            "is_suspended": device.get("status", {}).get("isSuspended", False),
            "test_dispatch_failure_reason": device.get("status", {}).get(
                "testDispatchFailureReason"
            ),
            "soc_limit_upper": (
                device.get("status", {}).get("stateOfChargeLimit", {}) or {}
            ).get("upperSocLimit"),
            "soc_limit_timestamp": (
                device.get("status", {}).get("stateOfChargeLimit", {}) or {}
            ).get("timestamp"),
            "soc_limit_violated": (
                device.get("status", {}).get("stateOfChargeLimit", {}) or {}
            ).get("isLimitViolated"),
            "alerts": device.get("alerts", []),
            "latest_alert_message": (
                device.get("alerts", [{}])[0].get("message")
                if device.get("alerts")
                else None
            ),
            "account_number": self._account_number,
            "last_updated": datetime.now().isoformat(),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        self._update_attributes()

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
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusElectricitySmartMeterReadingsSensor(
    CoordinatorEntity, SensorEntity, RestoreEntity
):
    """Sensor for displaying smart meter readings (previous day accumulative consumption)."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number

        # Use fallback values during initialization, will be updated when coordinator data is available
        self._attr_name = (
            f"Previous Accumulative Consumption Electricity ({account_number})"
        )
        self._attr_unique_id = f"octopus_germany_electricity_{account_number}_previous_accumulative_consumption"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL

        # Base attributes - will be updated when data is available
        self._attributes = {
            "account_number": account_number,
            "is_smart_meter": True,
        }

        self._state = None
        self._last_reset = None
        self._meter_info_cached = None

    def _get_meter_info(self) -> dict:
        """Get meter information from coordinator data."""
        if (
            self.coordinator.data
            and self._account_number in self.coordinator.data
            and "meter" in self.coordinator.data[self._account_number]
        ):
            return self.coordinator.data[self._account_number]["meter"]
        return {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        meter_info = self._get_meter_info()
        if meter_info and meter_info.get("number"):
            meter_number = meter_info["number"]
            return f"Previous Accumulative Consumption Electricity ({meter_number}/{self._account_number})"
        return f"Previous Accumulative Consumption Electricity ({self._account_number})"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added."""
        # Always enable - data availability will be handled by the available property
        return True

    @property
    def native_value(self) -> float | None:
        """Return the total consumption for the previous available day."""
        if (
            self.coordinator.data
            and self._account_number in self.coordinator.data
            and "electricity_smart_meter_readings"
            in self.coordinator.data[self._account_number]
        ):
            readings = self.coordinator.data[self._account_number][
                "electricity_smart_meter_readings"
            ]
            if readings and len(readings) > 0:
                # Calculate total consumption for the day, converting values to float
                total_consumption = 0.0
                for reading in readings:
                    value = reading.get("value", 0)
                    try:
                        # Convert string or numeric value to float
                        if isinstance(value, str):
                            total_consumption += float(value)
                        else:
                            total_consumption += float(value or 0)
                    except (ValueError, TypeError):
                        # Skip invalid values
                        continue
                return round(total_consumption, 3)
        return None

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset."""
        return self._last_reset

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return detailed attributes following Octopus Energy pattern."""
        if (
            self.coordinator.data
            and self._account_number in self.coordinator.data
            and "electricity_smart_meter_readings"
            in self.coordinator.data[self._account_number]
        ):
            readings = self.coordinator.data[self._account_number][
                "electricity_smart_meter_readings"
            ]
            if readings:
                # Calculate totals and create detailed breakdown
                total_consumption = 0.0
                for reading in readings:
                    value = reading.get("value", 0)
                    try:
                        # Convert string or numeric value to float
                        if isinstance(value, str):
                            total_consumption += float(value)
                        else:
                            total_consumption += float(value or 0)
                    except (ValueError, TypeError):
                        # Skip invalid values
                        continue

                # Create charges array similar to Octopus Energy
                charges = []
                for reading in readings:
                    value = reading.get("value", 0)
                    try:
                        # Convert to float for consistency
                        if isinstance(value, str):
                            consumption_value = float(value)
                        else:
                            consumption_value = float(value or 0)
                    except (ValueError, TypeError):
                        consumption_value = 0.0

                    charges.append(
                        {
                            "start": reading.get("start_time"),
                            "end": reading.get("end_time"),
                            "consumption": consumption_value,
                        }
                    )

                # Get date information
                date_info = self.coordinator.data[self._account_number].get(
                    "electricity_smart_meter_readings_date"
                )
                date_label = self.coordinator.data[self._account_number].get(
                    "electricity_smart_meter_readings_label", "previous day"
                )

                # Get meter info for attributes
                meter_info = self._get_meter_info()

                # Update base attributes with current data
                self._attributes.update(
                    {
                        "meter_id": meter_info.get("id"),
                        "meter_number": meter_info.get("number"),
                        "meter_type": meter_info.get("type"),
                        "total": round(
                            total_consumption, 6
                        ),  # More precision for total
                        "total_readings": len(readings),
                        "reading_date": date_info,
                        "reading_period": date_label,
                        "charges": charges,
                        "data_last_retrieved": self.coordinator.data[
                            self._account_number
                        ].get("last_updated"),
                    }
                )

                # Set last reset time to start of the day
                if readings and readings[0].get("start_time"):
                    try:
                        first_reading_time = datetime.fromisoformat(
                            readings[0]["start_time"].replace("Z", "+00:00")
                        )
                        self._last_reset = first_reading_time.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                    except (ValueError, TypeError):
                        pass

                return self._attributes

        return self._attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator is not None
            and self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._account_number in self.coordinator.data
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state if available
        if (state := await self.async_get_last_state()) is not None:
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._state = float(state.state)
                except (ValueError, TypeError):
                    pass

                # Restore attributes
                if state.attributes:
                    self._attributes.update(state.attributes)

        _LOGGER.debug(f"Restored smart meter sensor state: {self._state}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


