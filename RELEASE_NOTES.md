# Release Notes

## Version 0.0.86 (2026-03-16)

### Beta Focus

- Runtime options are now configurable from the Home Assistant options dialog.
- EV charging sensors and diagnostics were expanded for SmartFlex troubleshooting.
- The integration was prepared for the next beta phase with safer internal refactoring.

### New Features

- Added runtime options for:
  - polling interval
  - smart meter probing
  - extra debug diagnostics
- Added EV charging sensors for:
  - next dispatch start
  - next dispatch energy
  - last charging cost
  - last charging problem
  - charging diagnostics
  - latest device alert
  - target SOC
  - target time

### Improvements

- Added cache fallbacks for tariff, reading, and smart meter data to reduce temporary `unknown` states.
- Reduced noisy smart meter warning behavior when interval data is not available.
- Expanded debug mode with request summaries, account summaries, and device/session diagnostics.
- Fixed the Home Assistant options flow so runtime settings can be changed reliably.

### Internal Refactor

- Moved GraphQL query strings into `custom_components/octopus_germany/queries.py`.
- Moved shared debug helpers into `custom_components/octopus_germany/debug.py`.
- Started moving normalization logic into `custom_components/octopus_germany/models/normalizers.py`.
- Split EV-specific helpers and sensors into:
  - `custom_components/octopus_germany/entity_helpers.py`
  - `custom_components/octopus_germany/sensor_ev.py`

### Notes

- This remains a beta-focused release intended for validation in real Home Assistant setups.
- The new EV sensor split is intended to reduce risk for future changes, but should be treated as a structural beta step.

## Version 0.0.66 (2025-11-22)

### 🎉 New Features

#### Smart Charging Sessions Tracking
- **New Sensor**: `sensor.octopus_<account>_smart_charging_sessions`
  - Tracks smart charging sessions for Octopus SmartFlex rewards (30€/month with ≥5 smart charges)
  - Shows current month count and progress toward reward eligibility
  - Attributes include: session history, energy totals, qualified months, rewards earned
  - Auto-filters SMART vs BOOST charging types

#### Smart Meter Readings
- **New Sensor**: `sensor.octopus_<account>_previous_accumulative_consumption_electricity`
  - Displays previous day's total electricity consumption from smart meter
  - Hourly breakdown in attributes for detailed analysis
  - Persistent state restoration on Home Assistant restart
  - Auto-updates when smart meter data becomes available (typically 2+ days lag)

- **New Service**: `octopus_germany.get_smart_meter_readings`
  - Fetch historical smart meter data for any date (YYYY-MM-DD format)
  - Useful for backfilling data or analyzing specific periods
  - Results available via event: `octopus_germany_smart_meter_readings_result`

#### Device Organization
- **Service Device Grouping**: All entities now grouped under single service device per account
  - Device name: "Octopus Energy Germany (A-xxxxxxx)"
  - Type: SERVICE (cloud service, not hardware)
  - Configuration link to https://my.octopusenergy.de/
  - Cleaner device registry - no more scattered entities

### 🔧 Improvements

#### API Enhancements
- Added comprehensive GraphQL schema exploration (54,000+ lines)
- New charging sessions query with device type filtering
- Smart meter readings query with property-based filtering
- Multiple date range testing for data availability
- Enhanced error handling with detailed logging

#### Token Management
- Fixed token refresh logic to clear expired tokens before login
- Improved retry mechanism with exponential backoff
- Better handling of concurrent token refresh attempts
- Restored previous token on complete login failure

#### Code Quality
- All 22 entities now have consistent `device_info` property
- Proper use of `DeviceEntryType.SERVICE` enum
- Improved typing with `RestoreEntity` for persistent sensors
- Cleaner imports and consistent code formatting
- Fixed `OctopusGermanyOptionsFlow` initialization

### 📝 Configuration Changes

#### New Constants
- `EXPLORE_SCHEMA_ONCE`: Control schema exploration (debug feature)
- Service constants for smart meter readings:
  - `SERVICE_GET_SMART_METER_READINGS`
  - `ATTR_DATE`
  - `ATTR_PROPERTY_ID`

#### Updated Services Definition
- Added `get_smart_meter_readings` service configuration
- Includes validation for date format (YYYY-MM-DD)
- Optional property_id (uses first property if not specified)

### 🐛 Bug Fixes

- **Device Status Sensor**: Now properly filters by device_id (previously showed only first device)
- **Binary Sensor**: Added missing `device_info` property
- **Switches**: Added missing `device_info` property
- **Options Flow**: Fixed initialization to accept config_entry parameter correctly
- **Formatting**: Cleaned up line wrapping and improved readability

### 📖 Documentation Updates

- Updated README with:
  - Smart charging sessions sensor documentation
  - Smart meter readings sensor and service documentation
  - Device grouping explanation
  - Service examples and automation ideas
- Added detailed attribute descriptions for new sensors
- Clarified data availability timelines (smart meter data lag)

### 🔄 Migration Notes

**Automatic Migration** (no action required):
- Existing entities will automatically be grouped under service device on next HA restart
- All entity IDs remain unchanged
- Historical data is preserved

**New Functionality**:
- Smart charging sessions: Automatically created if you have SmartFlex devices
- Smart meter readings: Automatically created if you have electricity service
- Service device: Visible in Devices & Services after restart

### 🎯 Requirements

- Home Assistant 2024.1.0 or newer
- Python 3.11 or newer
- `python-graphql-client==0.4.3` (unchanged)

### 📊 Statistics

- **New Sensors**: 2 (Smart Charging Sessions, Smart Meter Readings)
- **New Services**: 1 (Get Smart Meter Readings)
- **Code Changes**: ~2,500+ lines added/modified
- **Files Changed**: 9 core files
- **Device Info Coverage**: 100% (22/22 entities)

### 🙏 Acknowledgments

Thanks to all users providing feedback and testing the integration!

### 📞 Support

For issues or questions:
- GitHub Issues: https://github.com/thecem/octopus_germany/issues
- Discussions: https://github.com/thecem/octopus_germany/discussions

---

## Previous Releases

### Version 0.0.65 (2025-11-22)

**Note**: Version 0.0.65 was released on GitHub with partial features.
Version 0.0.66 completes the implementation with all features fully documented.

### Version 0.0.64 (2025-09-22)

**Highlights**
 - Fix: Boost Charge switch could become unavailable due to independent coordinator using an expired JWT. The boost switch now uses the main coordinator and shared token handling.
 - Fix: Restored `boost_charge_active` and `boost_charge_available` attributes on the Boost Charge switch.
 - Cleanup: Removed remnants of deprecated `set_vehicle_charge_preferences` service and consolidated to `set_device_preferences`.
 - Docs: Updated `custom_components/octopus_germany/README.md` and added `TECHNICAL_NOTES.md` describing architecture, token management, and availability rules for the boost switch.
 - Repository: Rebased local `main` onto `origin/main` to reconcile divergent branches.

**Notes for integrators**
 - Boost Charge switch availability depends on the device being LIVE, not suspended, and supporting smart control/smart charging on the account.
 - If you maintain CI or local clones, consider choosing a default pull behavior to avoid repeated hints from Git. Example to set rebase as default:

  git config pull.rebase true

**Contact**
 - For questions or if you observe regressions, open an issue or attach logs from your Home Assistant instance.
