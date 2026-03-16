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


def extract_account_basics(
    account_data: dict[str, Any], logger: logging.Logger
) -> dict[str, Any]:
    """Extract account-wide identifiers, ledgers, and meter references."""
    ledgers = account_data.get("ledgers", [])
    electricity_balance_eur = 0.0
    gas_balance_eur = 0.0
    heat_balance_eur = 0.0
    other_ledgers: dict[str, float] = {}

    for ledger in ledgers:
        ledger_type = ledger.get("ledgerType")
        balance_cents = ledger.get("balance", 0)
        balance_eur = balance_cents / 100

        if ledger_type == "ELECTRICITY_LEDGER":
            electricity_balance_eur = balance_eur
        elif ledger_type == "GAS_LEDGER":
            gas_balance_eur = balance_eur
        elif ledger_type == "HEAT_LEDGER":
            heat_balance_eur = balance_eur
        else:
            other_ledgers[ledger_type] = balance_eur
            logger.debug(
                "Found additional ledger type: %s with balance: %.2f EUR",
                ledger_type,
                balance_eur,
            )

    all_properties = account_data.get("allProperties", [])

    malo_number = next(
        (
            malo.get("maloNumber")
            for prop in all_properties
            for malo in prop.get("electricityMalos", [])
            if malo.get("maloNumber")
        ),
        None,
    )
    melo_number = next(
        (
            malo.get("meloNumber")
            for prop in all_properties
            for malo in prop.get("electricityMalos", [])
            if malo.get("meloNumber")
        ),
        None,
    )
    gas_malo_number = next(
        (
            malo.get("maloNumber")
            for prop in all_properties
            for malo in prop.get("gasMalos", [])
            if malo.get("maloNumber")
        ),
        None,
    )
    gas_melo_number = next(
        (
            malo.get("meloNumber")
            for prop in all_properties
            for malo in prop.get("gasMalos", [])
            if malo.get("meloNumber")
        ),
        None,
    )

    meter = None
    gas_meter = None
    for prop in all_properties:
        for malo in prop.get("electricityMalos", []):
            if malo.get("meter"):
                meter = malo.get("meter")
                break
        if meter:
            break

    for prop in all_properties:
        for malo in prop.get("gasMalos", []):
            if malo.get("meter"):
                gas_meter = malo.get("meter")
                break
        if gas_meter:
            break

    property_ids = [prop.get("id") for prop in all_properties]

    return {
        "ledgers": ledgers,
        "electricity_balance": electricity_balance_eur,
        "gas_balance": gas_balance_eur,
        "heat_balance": heat_balance_eur,
        "other_ledgers": other_ledgers,
        "malo_number": malo_number,
        "melo_number": melo_number,
        "meter": meter,
        "gas_malo_number": gas_malo_number,
        "gas_melo_number": gas_melo_number,
        "gas_meter": gas_meter,
        "property_ids": property_ids,
    }


def _extract_gross_rate(value: Any) -> str:
    """Extract a gross rate from a dict/list GraphQL payload."""
    if isinstance(value, dict):
        return value.get("grossRate", "0")
    if isinstance(value, list) and value:
        return value[0].get("grossRate", "0")
    return "0"


def extract_electricity_products(
    data: dict[str, Any], account_data: dict[str, Any], logger: logging.Logger
) -> list[dict[str, Any]]:
    """Extract normalized electricity products from direct or nested account data."""
    products: list[dict[str, Any]] = []
    direct_products = data.get("direct_products", [])

    for product in direct_products:
        gross_rate = _extract_gross_rate(product.get("grossRateInformation"))
        products.append(
            {
                "code": product.get("code", "Unknown"),
                "description": product.get("description", ""),
                "name": product.get("fullName", "Unknown"),
                "grossRate": gross_rate,
                "type": "Simple",
                "validFrom": None,
                "validTo": None,
                "isTimeOfUse": product.get("isTimeOfUse", False),
            }
        )

    if products:
        return products

    logger.debug("Extracting products from account data")

    for prop in account_data.get("allProperties", []):
        for malo in prop.get("electricityMalos", []):
            for agreement in malo.get("agreements", []):
                product = agreement.get("product", {})
                unit_rate_info = agreement.get("unitRateInformation", {})

                if unit_rate_info:
                    logger.debug(
                        "Unit rate info keys: %s", list(unit_rate_info.keys())
                    )

                product_type = "Simple"
                if "__typename" in unit_rate_info:
                    product_type = (
                        "Simple"
                        if unit_rate_info["__typename"]
                        == "SimpleProductUnitRateInformation"
                        else "TimeOfUse"
                    )

                if product_type == "Simple":
                    gross_rate = "0"
                    if "grossRateInformation" in unit_rate_info:
                        gross_rate = _extract_gross_rate(
                            unit_rate_info["grossRateInformation"]
                        )
                    elif "latestGrossUnitRateCentsPerKwh" in unit_rate_info:
                        gross_rate = unit_rate_info["latestGrossUnitRateCentsPerKwh"]
                    elif "unitRateGrossRateInformation" in agreement:
                        gross_rate = _extract_gross_rate(
                            agreement["unitRateGrossRateInformation"]
                        )

                    products.append(
                        {
                            "code": product.get("code", "Unknown"),
                            "description": product.get("description", ""),
                            "name": product.get("fullName", "Unknown"),
                            "grossRate": gross_rate,
                            "type": product_type,
                            "validFrom": agreement.get("validFrom"),
                            "validTo": agreement.get("validTo"),
                            "isTimeOfUse": product.get("isTimeOfUse", False),
                            "unitRateForecast": agreement.get("unitRateForecast", []),
                        }
                    )
                elif product_type == "TimeOfUse" and "rates" in unit_rate_info:
                    timeslots = []
                    for rate in unit_rate_info["rates"]:
                        gross_rate = "0"
                        if "grossRateInformation" in rate and rate["grossRateInformation"]:
                            gross_rate = _extract_gross_rate(rate["grossRateInformation"])
                        elif "latestGrossUnitRateCentsPerKwh" in rate:
                            gross_rate = rate["latestGrossUnitRateCentsPerKwh"]

                        activation_rules = []
                        if "timeslotActivationRules" in rate and isinstance(
                            rate["timeslotActivationRules"], list
                        ):
                            for rule in rate["timeslotActivationRules"]:
                                activation_rules.append(
                                    {
                                        "from_time": rule.get(
                                            "activeFromTime", "00:00:00"
                                        ),
                                        "to_time": rule.get(
                                            "activeToTime", "00:00:00"
                                        ),
                                    }
                                )

                        timeslots.append(
                            {
                                "name": rate.get("timeslotName", "Unknown"),
                                "rate": gross_rate,
                                "activation_rules": activation_rules,
                            }
                        )

                    products.append(
                        {
                            "code": product.get("code", "Unknown"),
                            "description": product.get("description", ""),
                            "name": product.get("fullName", "Unknown"),
                            "type": product_type,
                            "validFrom": agreement.get("validFrom"),
                            "validTo": agreement.get("validTo"),
                            "timeslots": timeslots,
                            "isTimeOfUse": product.get("isTimeOfUse", False),
                            "unitRateForecast": agreement.get("unitRateForecast", []),
                        }
                    )

                    logger.debug(
                        "Found TimeOfUse product with %d timeslots: %s",
                        len(timeslots),
                        [timeslot.get("name") for timeslot in timeslots],
                    )

    return products


def extract_gas_products(
    account_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract normalized gas products from account data."""
    gas_products: list[dict[str, Any]] = []

    for prop in account_data.get("allProperties", []):
        for malo in prop.get("gasMalos", []):
            for agreement in malo.get("agreements", []):
                product = agreement.get("product", {})
                unit_rate_info = agreement.get("unitRateInformation", {})

                product_type = "Simple"
                if "__typename" in unit_rate_info:
                    product_type = (
                        "Simple"
                        if unit_rate_info["__typename"]
                        == "SimpleProductUnitRateInformation"
                        else "TimeOfUse"
                    )

                if product_type == "Simple":
                    gross_rate = "0"
                    if "grossRateInformation" in unit_rate_info:
                        gross_rate = _extract_gross_rate(
                            unit_rate_info["grossRateInformation"]
                        )
                    elif "latestGrossUnitRateCentsPerKwh" in unit_rate_info:
                        gross_rate = unit_rate_info["latestGrossUnitRateCentsPerKwh"]
                    elif "unitRateGrossRateInformation" in agreement:
                        gross_rate = _extract_gross_rate(
                            agreement["unitRateGrossRateInformation"]
                        )

                    gas_products.append(
                        {
                            "code": product.get("code", "Unknown"),
                            "description": product.get("description", ""),
                            "name": product.get("fullName", "Unknown"),
                            "grossRate": gross_rate,
                            "type": product_type,
                            "validFrom": agreement.get("validFrom"),
                            "validTo": agreement.get("validTo"),
                            "isTimeOfUse": product.get("isTimeOfUse", False),
                        }
                    )
                elif product_type == "TimeOfUse" and "rates" in unit_rate_info:
                    timeslots = []
                    for rate in unit_rate_info["rates"]:
                        gross_rate = "0"
                        if "grossRateInformation" in rate:
                            gross_rate = _extract_gross_rate(rate["grossRateInformation"])
                        elif "latestGrossUnitRateCentsPerKwh" in rate:
                            gross_rate = rate["latestGrossUnitRateCentsPerKwh"]

                        activation_rules = []
                        for rule in rate.get("timeslotActivationRules", []):
                            activation_rules.append(
                                {
                                    "from_time": rule.get("activeFromTime", "00:00:00"),
                                    "to_time": rule.get("activeToTime", "00:00:00"),
                                }
                            )

                        timeslots.append(
                            {
                                "name": rate.get("timeslotName", "Unknown"),
                                "rate": gross_rate,
                                "activation_rules": activation_rules,
                            }
                        )

                    gas_products.append(
                        {
                            "code": product.get("code", "Unknown"),
                            "description": product.get("description", ""),
                            "name": product.get("fullName", "Unknown"),
                            "grossRate": "0",
                            "type": product_type,
                            "validFrom": agreement.get("validFrom"),
                            "validTo": agreement.get("validTo"),
                            "timeslots": timeslots,
                            "isTimeOfUse": product.get("isTimeOfUse", False),
                        }
                    )

    return gas_products


def derive_current_gas_product_details(
    gas_products: list[dict[str, Any]],
) -> tuple[float | None, str | None, str | None]:
    """Derive current gas price and contract dates from gas products."""
    gas_price = None
    gas_contract_start = None
    gas_contract_end = None

    if not gas_products:
        return gas_price, gas_contract_start, gas_contract_end

    now = datetime.now().isoformat()
    valid_gas_products = [
        product for product in gas_products if is_currently_valid_product(product, now)
    ]
    if not valid_gas_products:
        return gas_price, gas_contract_start, gas_contract_end

    valid_gas_products.sort(key=lambda product: product.get("validFrom", ""), reverse=True)
    current_gas_product = valid_gas_products[0]

    try:
        gas_price = float(current_gas_product.get("grossRate", "0")) / 100.0
    except (ValueError, TypeError):
        gas_price = None

    gas_contract_start = current_gas_product.get("validFrom")
    gas_contract_end = current_gas_product.get("validTo")
    return gas_price, gas_contract_start, gas_contract_end


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
