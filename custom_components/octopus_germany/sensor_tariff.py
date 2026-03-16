"""Tariff and balance sensors for Octopus Germany."""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any, Dict

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity_helpers import get_account_device_info

_LOGGER = logging.getLogger(__name__)


def build_tariff_entities(account_number: str, coordinator, account_data: dict) -> list:
    """Build tariff- and balance-related sensor entities for one account."""
    entities = []

    if account_data.get("malo_number") and account_data.get("products", []):
        entities.append(OctopusElectricityPriceSensor(account_number, coordinator))

    if "electricity_balance" in account_data and account_data.get("malo_number"):
        entities.append(OctopusElectricityBalanceSensor(account_number, coordinator))

    if account_data.get("gas_malo_number"):
        if "gas_balance" in account_data and account_data.get("gas_malo_number"):
            entities.append(OctopusGasBalanceSensor(account_number, coordinator))

        if account_data.get("gas_products", []):
            entities.append(OctopusGasTariffSensor(account_number, coordinator))

    if "heat_balance" in account_data and account_data.get("heat_balance", 0) != 0:
        entities.append(OctopusHeatBalanceSensor(account_number, coordinator))

    for ledger_type in account_data.get("other_ledgers", {}):
        entities.append(
            OctopusLedgerBalanceSensor(account_number, coordinator, ledger_type)
        )

    return entities

class OctopusElectricityPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany electricity price."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the electricity price sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Electricity Price"
        self._attr_unique_id = f"octopus_{account_number}_electricity_price"
        self._attr_native_unit_of_measurement = "EUR/kWh"
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    def _parse_time(self, time_str: str) -> time:
        """Parse time string in HH:MM:SS format to time object."""
        try:
            hour, minute, second = map(int, time_str.split(":"))
            return time(hour=hour, minute=minute, second=second)
        except (ValueError, AttributeError):
            _LOGGER.error(f"Invalid time format: {time_str}")
            return None

    def _is_time_between(
        self, current_time: time, time_from: time, time_to: time
    ) -> bool:
        """Check if current_time is between time_from and time_to."""
        # Handle special case where time_to is 00:00:00 (midnight)
        if time_to.hour == 0 and time_to.minute == 0 and time_to.second == 0:
            # If time_from is also midnight, the slot is active all day
            if time_from.hour == 0 and time_from.minute == 0 and time_from.second == 0:
                return True
            # Otherwise, the slot is active from time_from until midnight, or from midnight until time_from
            return current_time >= time_from or current_time < time_to
        # Normal case: check if time is between start and end
        elif time_from <= time_to:
            return time_from <= current_time < time_to
        # Handle case where range crosses midnight
        else:
            return time_from <= current_time or current_time < time_to

    def _get_active_timeslot_rate(self, product):
        """Get the currently active timeslot rate for a time-of-use product."""
        if not product:
            return None

        # For SimpleProductUnitRateInformation, just return the single rate
        if product.get("type") == "Simple":
            try:
                # Convert to float but don't round - divide by 100 to convert from cents to euros
                return float(product.get("grossRate", "0")) / 100.0
            except (ValueError, TypeError):
                return None

        # For TimeOfUseProductUnitRateInformation, find the currently active timeslot
        if product.get("type") == "TimeOfUse" and "timeslots" in product:
            current_time = datetime.now().time()

            for timeslot in product["timeslots"]:
                for rule in timeslot.get("activation_rules", []):
                    from_time = self._parse_time(rule.get("from_time", "00:00:00"))
                    to_time = self._parse_time(rule.get("to_time", "00:00:00"))

                    if (
                        from_time
                        and to_time
                        and self._is_time_between(current_time, from_time, to_time)
                    ):
                        try:
                            # Convert to float but don't round - divide by 100 to convert from cents to euros
                            return float(timeslot.get("rate", "0")) / 100.0
                        except (ValueError, TypeError):
                            continue

        # If no active timeslot found or in case of errors, return None
        return None

    def _get_current_forecast_rate(self, product):
        """Get the current rate from unitRateForecast for dynamic pricing."""
        if not product:
            return None

        unit_rate_forecast = product.get("unitRateForecast", [])
        if not unit_rate_forecast:
            return None

        now = datetime.now(timezone.utc)

        # Find the forecast entry that covers the current time
        for forecast_entry in unit_rate_forecast:
            valid_from_str = forecast_entry.get("validFrom")
            valid_to_str = forecast_entry.get("validTo")

            if not valid_from_str or not valid_to_str:
                continue

            try:
                # Parse the time stamps
                valid_from = datetime.fromisoformat(
                    valid_from_str.replace("Z", "+00:00")
                )
                valid_to = datetime.fromisoformat(valid_to_str.replace("Z", "+00:00"))

                # Check if current time is within this forecast period
                if valid_from <= now < valid_to:
                    # Extract the rate from unitRateInformation
                    unit_rate_info = forecast_entry.get("unitRateInformation", {})

                    if (
                        unit_rate_info.get("__typename")
                        == "TimeOfUseProductUnitRateInformation"
                    ):
                        rates = unit_rate_info.get("rates", [])
                        if rates and len(rates) > 0:
                            rate_cents = rates[0].get("latestGrossUnitRateCentsPerKwh")
                            if rate_cents is not None:
                                try:
                                    rate_eur = float(rate_cents) / 100.0
                                    _LOGGER.debug(
                                        "Found forecast rate: %.4f EUR/kWh for period %s - %s",
                                        rate_eur,
                                        valid_from_str,
                                        valid_to_str,
                                    )
                                    return rate_eur
                                except (ValueError, TypeError):
                                    continue

            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Error parsing forecast entry: %s - %s", forecast_entry, str(e)
                )
                continue

        _LOGGER.debug(
            "No current forecast rate found for current time %s", now.isoformat()
        )
        return None

    @property
    def native_value(self) -> float:
        """Return the current electricity price."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            _LOGGER.warning("No valid coordinator data found for price sensor")
            return None

        account_data = self.coordinator.data[self._account_number]
        products = account_data.get("products", [])

        if not products:
            _LOGGER.warning("No products found in coordinator data")
            return None

        # Find the current valid product based on validity dates
        now = datetime.now().isoformat()
        valid_products = []

        # First filter products that are currently valid
        for product in products:
            valid_from = product.get("validFrom")
            valid_to = product.get("validTo")

            # Skip products without validity information
            if not valid_from:
                continue

            # Check if product is currently valid
            if valid_from <= now and (not valid_to or now <= valid_to):
                valid_products.append(product)

        # If we have valid products, use the one with the latest validFrom
        if valid_products:
            # Sort by validFrom in descending order to get the most recent one
            valid_products.sort(key=lambda p: p.get("validFrom", ""), reverse=True)
            current_product = valid_products[0]

            product_code = current_product.get("code", "Unknown")
            product_type = current_product.get("type", "Unknown")

            _LOGGER.debug(
                "Using product: %s, type: %s, valid from: %s",
                product_code,
                product_type,
                current_product.get("validFrom", "Unknown"),
            )

            if current_product.get("isTimeOfUse", False):
                # For dynamic TimeOfUse tariffs, use unitRateForecast data
                forecast_rate = self._get_current_forecast_rate(current_product)
                if forecast_rate is not None:
                    _LOGGER.debug(
                        "Dynamic forecast price: %.4f EUR/kWh for product %s",
                        forecast_rate,
                        product_code,
                    )
                    return forecast_rate

                # Fallback to timeslot rate if no forecast available
                if product_type == "TimeOfUse":
                    active_rate = self._get_active_timeslot_rate(current_product)
                    if active_rate is not None:
                        _LOGGER.debug(
                            "Fallback timeslot price: %.4f EUR/kWh for product %s",
                            active_rate,
                            product_code,
                        )
                        return active_rate

            # For simple tariffs or fallback, use the gross rate
            try:
                gross_rate_str = current_product.get("grossRate", "0")
                gross_rate = float(gross_rate_str)
                # Convert from cents to EUR without rounding
                base_rate_eur = gross_rate / 100.0

                _LOGGER.debug(
                    "Price: %.4f EUR/kWh for product %s", base_rate_eur, product_code
                )
                return base_rate_eur
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Failed to convert price for product %s: %s - %s",
                    product_code,
                    current_product.get("grossRate", "Unknown"),
                    str(e),
                )

        _LOGGER.warning("No valid product found for current date")
        return None

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        # Default empty attributes
        default_attributes = {
            "code": "Unknown",
            "name": "Unknown",
            "description": "Unknown",
            "type": "Unknown",
            "valid_from": "Unknown",
            "valid_to": "Unknown",
            "meter_id": "Unknown",
            "meter_number": "Unknown",
            "meter_type": "Unknown",
            "account_number": self._account_number,
        }

        # Check if coordinator has valid data
        if (
            not self.coordinator
            or not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
        ):
            _LOGGER.debug("No valid data structure in coordinator")
            self._attributes = default_attributes
            return

        # Check if account number exists in the data
        if self._account_number not in self.coordinator.data:
            _LOGGER.debug(
                "Account %s not found in coordinator data", self._account_number
            )
            self._attributes = default_attributes
            return

        # Process data from the coordinator
        account_data = self.coordinator.data[self._account_number]
        products = account_data.get("products", [])

        # Extract meter information directly
        meter_data = account_data.get("meter", {})
        meter_id = "Unknown"
        meter_number = "Unknown"
        meter_type = "Unknown"

        if meter_data and isinstance(meter_data, dict):
            meter_id = meter_data.get("id", "Unknown")
            meter_number = meter_data.get("number", "Unknown")
            meter_type = meter_data.get("meterType", "Unknown")
            _LOGGER.debug(
                f"Found meter info: id={meter_id}, number={meter_number}, type={meter_type}"
            )

        if not products:
            self._attributes = {
                **default_attributes,
                "meter_id": meter_id,
                "meter_number": meter_number,
                "meter_type": meter_type,
            }
            return

        # Find the current valid product based on validity dates
        now = datetime.now().isoformat()
        valid_products = []

        # First filter products that are currently valid
        for product in products:
            valid_from = product.get("validFrom")
            valid_to = product.get("validTo")

            # Skip products without validity information
            if not valid_from:
                continue

            # Check if product is currently valid
            if valid_from <= now and (not valid_to or now <= valid_to):
                valid_products.append(product)

        # If we have valid products, use the one with the latest validFrom
        if valid_products:
            # Sort by validFrom in descending order to get the most recent one
            valid_products.sort(key=lambda p: p.get("validFrom", ""), reverse=True)
            current_product = valid_products[0]

            # Extract attribute values from the product
            product_attributes = {
                "code": current_product.get("code", "Unknown"),
                "name": current_product.get("name", "Unknown"),
                "description": current_product.get("description", "Unknown"),
                "type": current_product.get("type", "Unknown"),
                "valid_from": current_product.get("validFrom", "Unknown"),
                "valid_to": current_product.get("validTo", "Unknown"),
                "meter_id": meter_id,
                "meter_number": meter_number,
                "meter_type": meter_type,
                "account_number": self._account_number,
                "active_tariff_type": current_product.get("type", "Unknown"),
            }

            # Add time-of-use specific information if available
            if (
                current_product.get("type") == "TimeOfUse"
                and "timeslots" in current_product
            ):
                current_time = datetime.now().time()
                active_timeslot = None
                timeslots_data = []

                # Get information about all timeslots and find active one
                for timeslot in current_product.get("timeslots", []):
                    timeslot_data = {
                        "name": timeslot.get("name", "Unknown"),
                        "rate": timeslot.get("rate", "0"),
                        "activation_rules": [],
                    }

                    # Add all activation rules
                    for rule in timeslot.get("activation_rules", []):
                        from_time = rule.get("from_time", "00:00:00")
                        to_time = rule.get("to_time", "00:00:00")
                        timeslot_data["activation_rules"].append(
                            {"from_time": from_time, "to_time": to_time}
                        )

                        # Check if this is the active timeslot
                        from_time_obj = self._parse_time(from_time)
                        to_time_obj = self._parse_time(to_time)
                        if (
                            from_time_obj
                            and to_time_obj
                            and self._is_time_between(
                                current_time, from_time_obj, to_time_obj
                            )
                        ):
                            active_timeslot = timeslot.get("name", "Unknown")
                            product_attributes["active_timeslot"] = active_timeslot
                            # Store the rate without rounding (convert from cents to euros)
                            product_attributes["active_timeslot_rate"] = (
                                float(timeslot.get("rate", "0")) / 100.0
                            )
                            product_attributes["active_timeslot_from"] = from_time
                            product_attributes["active_timeslot_to"] = to_time

                    timeslots_data.append(timeslot_data)

                product_attributes["timeslots"] = timeslots_data

            # Add any additional information from account data
            product_attributes["malo_number"] = account_data.get(
                "malo_number", "Unknown"
            )
            product_attributes["melo_number"] = account_data.get(
                "melo_number", "Unknown"
            )

            # Add electricity balance if available
            if "electricity_balance" in account_data:
                product_attributes["electricity_balance"] = (
                    f"{account_data['electricity_balance']:.2f} EUR"
                )

            # Add dual format rate data for compatibility
            if current_product.get("isTimeOfUse", False):
                # UK format for octopus-energy-rates-card compatibility
                uk_rates = self._format_uk_rates(current_product)
                product_attributes["rates"] = uk_rates
                product_attributes["rates_count"] = len(uk_rates)

                # German format for native tools
                product_attributes["unit_rate_forecast"] = current_product.get(
                    "unitRateForecast", []
                )

            self._attributes = product_attributes
        else:
            # If no valid products, use default attributes
            self._attributes = {
                **default_attributes,
                "meter_id": meter_id,
                "meter_number": meter_number,
                "meter_type": meter_type,
            }

    def _format_uk_rates(self, product):
        """Format unitRateForecast data into UK-style rates attribute."""
        if not product:
            return []

        unit_rate_forecast = product.get("unitRateForecast", [])
        if not unit_rate_forecast:
            return []

        all_rates = []

        for forecast_entry in unit_rate_forecast:
            valid_from_str = forecast_entry.get("validFrom")
            valid_to_str = forecast_entry.get("validTo")

            if not valid_from_str or not valid_to_str:
                continue

            try:
                # Extract rate information
                unit_rate_info = forecast_entry.get("unitRateInformation", {})
                price_eur_kwh = None

                if (
                    unit_rate_info.get("__typename")
                    == "SimpleProductUnitRateInformation"
                ):
                    rate_cents = unit_rate_info.get("latestGrossUnitRateCentsPerKwh")
                    if rate_cents is not None:
                        price_eur_kwh = float(rate_cents) / 100.0

                elif (
                    unit_rate_info.get("__typename")
                    == "TimeOfUseProductUnitRateInformation"
                ):
                    rates = unit_rate_info.get("rates", [])
                    if rates and len(rates) > 0:
                        rate_cents = rates[0].get("latestGrossUnitRateCentsPerKwh")
                        if rate_cents is not None:
                            price_eur_kwh = float(rate_cents) / 100.0

                if price_eur_kwh is not None:
                    all_rates.append(
                        {
                            "start": valid_from_str,
                            "end": valid_to_str,
                            "value_inc_vat": round(price_eur_kwh, 4),
                        }
                    )

            except (ValueError, TypeError) as e:
                _LOGGER.debug("Error processing forecast entry: %s", e)
                continue

        # Sort by start time
        all_rates.sort(key=lambda x: x["start"])

        _LOGGER.debug("Formatted %d rates for UK compatibility", len(all_rates))
        return all_rates

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
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas balance."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas balance sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Balance"
        self._attr_unique_id = f"octopus_{account_number}_gas_balance"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> float:
        """Return the gas balance."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("gas_balance", 0.0)

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
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusElectricityBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany electricity balance."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the electricity balance sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Electricity Balance"
        self._attr_unique_id = f"octopus_{account_number}_electricity_balance"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> float:
        """Return the electricity balance."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("electricity_balance", 0.0)

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
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusHeatBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany heat balance."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the heat balance sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Heat Balance"
        self._attr_unique_id = f"octopus_{account_number}_heat_balance"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> float:
        """Return the heat balance."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        return account_data.get("heat_balance", 0.0)

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
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusLedgerBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany generic ledger balance."""

    def __init__(self, account_number, coordinator, ledger_type) -> None:
        """Initialize the ledger balance sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._ledger_type = ledger_type
        ledger_name = ledger_type.replace("_LEDGER", "").replace("_", " ").title()
        self._attr_name = f"Octopus {account_number} {ledger_name} Balance"
        self._attr_unique_id = f"octopus_{account_number}_{ledger_type.lower()}_balance"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_has_entity_name = False

    @property
    def native_value(self) -> float:
        """Return the ledger balance."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            return None

        account_data = self.coordinator.data[self._account_number]
        other_ledgers = account_data.get("other_ledgers", {})
        return other_ledgers.get(self._ledger_type, 0.0)

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
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


class OctopusGasTariffSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Octopus Germany gas tariff."""

    def __init__(self, account_number, coordinator) -> None:
        """Initialize the gas tariff sensor."""
        super().__init__(coordinator)

        self._account_number = account_number
        self._attr_name = f"Octopus {account_number} Gas Tariff"
        self._attr_unique_id = f"octopus_{account_number}_gas_tariff"
        self._attr_has_entity_name = False
        self._attributes = {}

        # Initialize attributes right after creation
        self._update_attributes()

    @property
    def native_value(self) -> str | None:
        """Return the current gas tariff code."""
        if (
            not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
            or self._account_number not in self.coordinator.data
        ):
            _LOGGER.warning("No valid coordinator data found for gas tariff sensor")
            return None

        account_data = self.coordinator.data[self._account_number]
        gas_products = account_data.get("gas_products", [])

        if not gas_products:
            _LOGGER.warning("No gas products found in coordinator data")
            return None

        # Find the current valid product based on validity dates
        now = datetime.now().isoformat()
        valid_products = []

        # First filter products that are currently valid
        for product in gas_products:
            valid_from = product.get("validFrom")
            valid_to = product.get("validTo")

            # Skip products without validity information
            if not valid_from:
                continue

            # Check if product is currently valid
            if valid_from <= now and (not valid_to or now <= valid_to):
                valid_products.append(product)

        # If we have valid products, use the one with the latest validFrom
        if valid_products:
            # Sort by validFrom in descending order to get the most recent one
            valid_products.sort(key=lambda p: p.get("validFrom", ""), reverse=True)
            current_product = valid_products[0]

            return current_product.get("code", "Unknown")

        _LOGGER.warning("No valid gas product found for current date")
        return None

    def _update_attributes(self) -> None:
        """Update the internal attributes dictionary."""
        # Default empty attributes - only tariff-specific info
        default_attributes = {
            "code": "Unknown",
            "name": "Unknown",
            "description": "Unknown",
            "type": "Unknown",
            "valid_from": "Unknown",
            "valid_to": "Unknown",
            "account_number": self._account_number,
        }

        # Check if coordinator has valid data
        if (
            not self.coordinator
            or not self.coordinator.data
            or not isinstance(self.coordinator.data, dict)
        ):
            _LOGGER.debug("No valid data structure in coordinator")
            self._attributes = default_attributes
            return

        # Check if account number exists in the data
        if self._account_number not in self.coordinator.data:
            _LOGGER.debug(
                "Account %s not found in coordinator data", self._account_number
            )
            self._attributes = default_attributes
            return

        # Process data from the coordinator
        account_data = self.coordinator.data[self._account_number]
        gas_products = account_data.get("gas_products", [])

        if not gas_products:
            self._attributes = default_attributes
            return

        # Find the current valid product based on validity dates
        now = datetime.now().isoformat()
        valid_products = []

        # First filter products that are currently valid
        for product in gas_products:
            valid_from = product.get("validFrom")
            valid_to = product.get("validTo")

            # Skip products without validity information
            if not valid_from:
                continue

            # Check if product is currently valid
            if valid_from <= now and (not valid_to or now <= valid_to):
                valid_products.append(product)

        # If we have valid products, use the one with the latest validFrom
        if valid_products:
            # Sort by validFrom in descending order to get the most recent one
            valid_products.sort(key=lambda p: p.get("validFrom", ""), reverse=True)
            current_product = valid_products[0]

            # Extract attribute values from the product - only tariff info
            product_attributes = {
                "code": current_product.get("code", "Unknown"),
                "name": current_product.get("name", "Unknown"),
                "description": current_product.get("description", "Unknown"),
                "type": current_product.get("type", "Unknown"),
                "valid_from": current_product.get("validFrom", "Unknown"),
                "valid_to": current_product.get("validTo", "Unknown"),
                "account_number": self._account_number,
            }

            # Add gas balance if available
            if "gas_balance" in account_data:
                product_attributes["gas_balance"] = (
                    f"{account_data['gas_balance']:.2f} EUR"
                )

            self._attributes = product_attributes
        else:
            # If no valid products, use default attributes
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
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_account_device_info(self._account_number)


