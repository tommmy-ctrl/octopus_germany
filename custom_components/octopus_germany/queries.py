"""GraphQL query definitions for the Octopus Germany integration."""

COMPREHENSIVE_QUERY = """
query ComprehensiveDataQuery($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    id
    ledgers {
      balance
      ledgerType
    }
    allProperties {
      id
      electricityMalos {
        agreements {
          product {
            code
            description
            fullName
            isTimeOfUse
          }
          unitRateGrossRateInformation {
            grossRate
          }
          unitRateInformation {
            ... on SimpleProductUnitRateInformation {
              __typename
              grossRateInformation {
                date
                grossRate
                rateValidToDate
                vatRate
              }
              latestGrossUnitRateCentsPerKwh
              netUnitRateCentsPerKwh
            }
            ... on TimeOfUseProductUnitRateInformation {
              __typename
              rates {
                grossRateInformation {
                  date
                  grossRate
                  rateValidToDate
                  vatRate
                }
                latestGrossUnitRateCentsPerKwh
                netUnitRateCentsPerKwh
                timeslotActivationRules {
                  activeFromTime
                  activeToTime
                }
                timeslotName
              }
            }
          }
          unitRateForecast {
            validFrom
            validTo
            unitRateInformation {
              __typename
              ... on SimpleProductUnitRateInformation {
                latestGrossUnitRateCentsPerKwh
              }
              ... on TimeOfUseProductUnitRateInformation {
                rates {
                  latestGrossUnitRateCentsPerKwh
                }
              }
            }
          }
          validFrom
          validTo
        }
        maloNumber
        meloNumber
        meter {
          id
          meterType
          number
          shouldReceiveSmartMeterData
          submitMeterReadingUrl
        }
        referenceConsumption
      }
      gasMalos {
        agreements {
          product {
            code
            description
            fullName
            isTimeOfUse
          }
          unitRateGrossRateInformation {
            grossRate
          }
          unitRateInformation {
            ... on SimpleProductUnitRateInformation {
              __typename
              grossRateInformation {
                date
                grossRate
                rateValidToDate
                vatRate
              }
              latestGrossUnitRateCentsPerKwh
              netUnitRateCentsPerKwh
            }
            ... on TimeOfUseProductUnitRateInformation {
              __typename
              rates {
                grossRateInformation {
                  date
                  grossRate
                  rateValidToDate
                  vatRate
                }
                latestGrossUnitRateCentsPerKwh
                netUnitRateCentsPerKwh
                timeslotActivationRules {
                  activeFromTime
                  activeToTime
                }
                timeslotName
              }
            }
          }
          validFrom
          validTo
        }
        maloNumber
        meloNumber
        meter {
          id
          meterType
          number
          shouldReceiveSmartMeterData
          submitMeterReadingUrl
        }
        referenceConsumption
      }
    }
  }
  completedDispatches(accountNumber: $accountNumber) {
    delta
    deltaKwh
    end
    endDt
    meta {
      location
      source
    }
    start
    startDt
  }
  devices(accountNumber: $accountNumber) {
    status {
      current
      currentState
      isSuspended
    }
    provider
    preferences {
      mode
      schedules {
        dayOfWeek
        max
        min
        time
      }
      targetType
      unit
      gridExport
    }
    preferenceSetting {
      deviceType
      id
      mode
      scheduleSettings {
        id
        max
        min
        step
        timeFrom
        timeStep
        timeTo
      }
      unit
    }
    name
    integrationDeviceId
    id
    deviceType
    alerts {
      message
      publishedAt
    }
    ... on SmartFlexVehicle {
      id
      name
      status {
        current
        currentState
        isSuspended
      }
      vehicleVariant {
        model
        batterySize
      }
      chargingSessions(first: 100) {
        edges {
          node {
            start
            end
            stateOfChargeChange
            stateOfChargeFinal
            energyAdded {
              value
              unit
            }
            cost {
              amount
              currency
            }
            ... on SmartFlexChargingSession {
              type
              targetType
              dispatches {
                start
                end
                type
              }
              problems {
                __typename
                ... on SmartFlexChargingError {
                  cause
                }
                ... on SmartFlexChargingTruncation {
                  truncationCause
                  originalAchievableStateOfCharge
                  achievableStateOfCharge
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    ... on SmartFlexChargePoint {
      chargingSessions(first: 100) {
        edges {
          node {
            start
            end
            stateOfChargeChange
            stateOfChargeFinal
            energyAdded {
              value
              unit
            }
            cost {
              amount
              currency
            }
            ... on SmartFlexChargingSession {
              type
              targetType
              dispatches {
                start
                end
                type
              }
              problems {
                __typename
                ... on SmartFlexChargingError {
                  cause
                }
                ... on SmartFlexChargingTruncation {
                  truncationCause
                  originalAchievableStateOfCharge
                  achievableStateOfCharge
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

GAS_METER_READINGS_QUERY = """
query GasMeterReadings($accountNumber: String!, $meterId: ID!) {
  gasMeterReadings(accountNumber: $accountNumber, meterId: $meterId, first: 1) {
    edges {
      node {
        value
        readAt
        registerObisCode
        typeOfRead
        origin
        meterId
      }
    }
  }
}
"""

ELECTRICITY_METER_READINGS_QUERY = """
query ElectricityMeterReadings($accountNumber: String!, $meterId: ID!) {
  electricityMeterReadings(accountNumber: $accountNumber, meterId: $meterId, first: 1) {
    edges {
      node {
        value
        readAt
        registerObisCode
        typeOfRead
        origin
        meterId
        registerType
      }
    }
  }
}
"""

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
    }
  }
}
"""

ALTERNATIVE_METER_READINGS_QUERY_1 = """
query getMeterReadings($accountNumber: String!, $propertyId: ID!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      electricityMeterPoints {
        id
        mpan
        meterReadings(first: 24) {
          edges {
            node {
              readAt
              value
              unit
              readingSource
            }
          }
        }
        meters {
          id
          serialNumber
          smartMeter
        }
      }
    }
  }
}
"""

ALTERNATIVE_METER_READINGS_QUERY_2 = """
query getPropertyMeasurements($accountNumber: String!, $propertyId: ID!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      id
      address {
        line1
        postcode
      }
      electricityMeterPoints {
        id
        mpan
        meters {
          id
          serialNumber
          smartMeter
          measurements(first: 24) {
            edges {
              node {
                ... on IntervalMeasurementType {
                  startAt
                  endAt
                  value
                  unit
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

PROPERTY_SCHEMA_QUERY = """
query PropertySchema($accountNumber: String!, $propertyId: ID!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      __typename
      id
      address {
        line1
        line2
        postcode
      }
      electricityMeterPoints {
        id
        mpan
        meterReadings(first: 5) {
          edges {
            node {
              readAt
              value
              unit
            }
          }
        }
        meters {
          id
          serialNumber
          smartMeter
        }
      }
      gasMeterPoints {
        id
        mprn
        meterReadings(first: 5) {
          edges {
            node {
              readAt
              value
              unit
            }
          }
        }
        meters {
          id
          serialNumber
          smartMeter
        }
      }
    }
  }
}
"""

ELECTRICITY_SMART_METER_READINGS_QUERY_V2 = """
query getSmartMeterUsageV2($accountNumber: String!, $propertyId: ID!, $date: Date!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      electricityMalos {
        meter {
          id
          number
          meterType
          shouldReceiveSmartMeterData
        }
        agreements {
          product {
            code
          }
        }
      }
      measurements(
        utilityFilters: {electricityFilters: {readingFrequencyType: HOUR_INTERVAL, readingQuality: COMBINED}}
        startOn: $date
        first: 24
      ) {
        edges {
          node {
            ... on IntervalMeasurementType {
              endAt
              startAt
              unit
              value
            }
          }
        }
      }
    }
  }
}
"""

ELECTRICITY_MALO_READINGS_QUERY = """
query getElectricityMaloReadings($accountNumber: String!, $propertyId: ID!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      electricityMalos {
        meter {
          id
          number
          meterType
          shouldReceiveSmartMeterData
          registers {
            obisCode
            registerType
            readings(first: 24) {
              edges {
                node {
                  value
                  readAt
                  typeOfRead
                  origin
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

ELECTRICITY_SMART_METER_READINGS_QUERY = """
query getSmartMeterUsage($accountNumber: String!, $propertyId: ID!, $date: Date!) {
  account(accountNumber: $accountNumber) {
    property(id: $propertyId) {
      measurements(
        utilityFilters: {electricityFilters: {readingFrequencyType: HOUR_INTERVAL, readingQuality: COMBINED}}
        startOn: $date
        first: 24
      ) {
        edges {
          node {
            ... on IntervalMeasurementType {
              endAt
              startAt
              unit
              value
            }
          }
        }
      }
    }
  }
}
"""

VEHICLE_DETAILS_QUERY = """
query Vehicle($accountNumber: String = "") {
  devices(accountNumber: $accountNumber) {
    deviceType
    id
    integrationDeviceId
    name
    preferenceSetting {
      deviceType
      id
      mode
      scheduleSettings {
        id
        max
        min
        step
        timeFrom
        timeStep
        timeTo
      }
      unit
    }
    preferences {
      gridExport
      mode
      targetType
      unit
    }
  }
}
"""

CHARGING_SESSIONS_QUERY = """
query ChargingSessions($accountNumber: String!) {
  devices(accountNumber: $accountNumber) {
    id
    deviceType
    name
    ... on SmartFlexVehicle {
      chargingSessions(first: 100) {
        edges {
          node {
            start
            end
            stateOfChargeChange
            stateOfChargeFinal
            energyAdded {
              value
              unit
            }
            cost {
              amount
              currency
            }
            ... on SmartFlexChargingSession {
              type
              targetType
              dispatches {
                start
                end
                type
              }
              problems {
                __typename
                ... on SmartFlexChargingError {
                  cause
                }
                ... on SmartFlexChargingTruncation {
                  truncationCause
                  originalAchievableStateOfCharge
                  achievableStateOfCharge
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    ... on SmartFlexChargePoint {
      chargingSessions(first: 100) {
        edges {
          node {
            start
            end
            stateOfChargeChange
            stateOfChargeFinal
            energyAdded {
              value
              unit
            }
            cost {
              amount
              currency
            }
            ... on SmartFlexChargingSession {
              type
              targetType
              dispatches {
                start
                end
                type
              }
              problems {
                __typename
                ... on SmartFlexChargingError {
                  cause
                }
                ... on SmartFlexChargingTruncation {
                  truncationCause
                  originalAchievableStateOfCharge
                  achievableStateOfCharge
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

ACCOUNT_DISCOVERY_QUERY = """
query {
  viewer {
    accounts {
      number
      ledgers {
        balance
        ledgerType
      }
    }
  }
}
"""
