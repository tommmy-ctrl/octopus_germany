# Octopus Germany Beta Roadmap

## Purpose

This roadmap keeps the integration in beta while improving stability, maintainability, and testability.

The focus is not "more features at any cost". The focus is:

- safer releases
- clearer internal structure
- better diagnostics
- fewer regressions

## Current Assessment

The integration is already useful and feature-rich, but several core files have grown too large:

- `custom_components/octopus_germany/octopus_germany.py`
- `custom_components/octopus_germany/__init__.py`
- `custom_components/octopus_germany/sensor.py`

Current risks:

- API logic, normalization, fallback handling, and Home Assistant integration logic are tightly coupled
- many flows still depend on untyped dictionaries
- query changes can break the main refresh path
- missing automated tests make refactors risky

## Beta Strategy

The project should continue as beta, but with stricter internal discipline:

1. keep user-facing behavior stable
2. reduce architectural risk in small steps
3. add tests before larger refactors
4. avoid large "rewrite" pull requests

## Release Phases

### Phase 1: Stabilize `0.0.x`

Goal: keep the current beta reliable.

Scope:

- bug fixes only in critical paths
- safer logging and diagnostics
- runtime options support
- cache fallback hardening
- avoid risky GraphQL query experiments in the main refresh query

Release gate:

- integration loads cleanly
- entities are created consistently
- options flow works
- no known regression in EV, smart meter, tariff, or dispatch entities

### Phase 2: Internal Separation `0.1.x`

Goal: reduce coupling without changing behavior.

Target structure:

- `custom_components/octopus_germany/api/client.py`
  - authentication
  - token management
  - GraphQL execution
  - response summary logging
- `custom_components/octopus_germany/api/queries.py`
  - query strings only
- `custom_components/octopus_germany/models/normalizers.py`
  - account data normalization
  - charging session normalization
  - dispatch normalization
- `custom_components/octopus_germany/models/types.py`
  - `TypedDict` or dataclass models for account/device/session/dispatch payloads
- `custom_components/octopus_germany/debug.py`
  - shared debug helpers

Recommended PR order:

1. move query strings out of `octopus_germany.py`
2. move normalization helpers out of `__init__.py`
3. centralize debug helpers
4. introduce typed models for new code paths first

Release gate:

- no user-visible breaking changes
- imports stay backwards compatible inside the integration
- existing entities and services keep their IDs and behavior

### Phase 3: Entity Split `0.2.x`

Goal: make platform code maintainable.

Target structure:

- `custom_components/octopus_germany/sensor_account.py`
- `custom_components/octopus_germany/sensor_tariff.py`
- `custom_components/octopus_germany/sensor_meter.py`
- `custom_components/octopus_germany/sensor_ev.py`

Optional later split:

- `switch_device.py`
- `switch_ev.py`
- `binary_sensor_dispatch.py`

Guidelines:

- keep common account/device lookup helpers in one shared module or base class
- avoid duplicating coordinator parsing logic across files
- separate EV logic from tariff and meter logic

Release gate:

- entity registry remains stable
- unique IDs remain unchanged
- no platform import regressions

### Phase 4: Test Foundation `0.3.x`

Goal: make changes safer.

Minimum test coverage:

- config flow
- options flow
- account data normalization
- fallback behavior when API data is partially missing
- charging session normalization
- dispatch selection logic

Recommended fixtures:

- normal account with electricity only
- account with gas and electricity
- account with no products
- account with no smart meter interval data
- EV session with truncation
- EV session with error
- partial GraphQL response with non-critical errors

Release gate:

- new logic ships with tests
- fixes for regressions get a matching regression test where practical

### Phase 5: Beta Hardening `0.4.x`

Goal: prepare for a more public and stable beta line.

Scope:

- improve release notes discipline
- document known limitations clearly
- standardize debug/reporting instructions
- create a lightweight pre-release checklist

Checklist:

1. config flow works
2. options flow works
3. integration setup succeeds on clean install
4. entity creation succeeds for at least one EV account and one non-EV account
5. no accidental breaking change in entity IDs or services
6. documentation updated

## Non-Goals For Beta

The following should not be attempted as one large step:

- complete rewrite of the integration
- replacing all dicts with dataclasses in one PR
- redesigning every entity platform at once
- aggressive new feature expansion during internal refactor phases

## Coding Rules For Beta Refactors

- one architectural concern per PR
- no query changes mixed with unrelated entity refactors
- no entity renames without strong reason
- preserve unique IDs and service names
- document any runtime option or diagnostics change
- if a refactor touches refresh logic, test fallback behavior explicitly

## Highest-Value Next Steps

If work starts now, the best order is:

1. extract GraphQL query strings to `api/queries.py`
2. extract `process_api_data()` support logic into `models/normalizers.py`
3. move EV-specific sensors into a dedicated sensor module
4. add tests for normalization and options flow

## Beta Exit Criteria

The project can still remain beta after this roadmap, but it should not leave beta until:

- core refresh logic is modularized
- config/options flows are stable
- fallback behavior is covered by tests
- EV diagnostics and smart meter behavior are documented
- maintainers can ship fixes without fear of breaking unrelated sensors
