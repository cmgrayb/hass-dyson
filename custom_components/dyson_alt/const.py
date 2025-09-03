"""Constants for the Dyson Alternative integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "dyson_alt"

# Default values
DEFAULT_CLOUD_POLLING_INTERVAL: Final = 300  # 5 minutes in seconds
DEFAULT_DEVICE_POLLING_INTERVAL: Final = (
    300  # 5 minutes for connectivity checks only (devices send natural STATE-CHANGE messages)
)
DEFAULT_TIMEOUT: Final = 10  # 10 seconds for network operations

# Configuration keys
CONF_DEVICE_TYPE: Final = "device_type"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_DEVICE_NAME: Final = "device_name"
CONF_CREDENTIAL: Final = "credential"
CONF_HOSTNAME: Final = "hostname"
CONF_CAPABILITIES: Final = "capabilities"
CONF_DISCOVERY_METHOD: Final = "discovery_method"
CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_MQTT_PREFIX: Final = "mqtt_prefix"

# Connection types
CONNECTION_TYPE_LOCAL_ONLY: Final = "local_only"
CONNECTION_TYPE_LOCAL_CLOUD_FALLBACK: Final = "local_cloud_fallback"
CONNECTION_TYPE_CLOUD_LOCAL_FALLBACK: Final = "cloud_local_fallback"
CONNECTION_TYPE_CLOUD_ONLY: Final = "cloud_only"

# Discovery methods
DISCOVERY_CLOUD: Final = "cloud"
DISCOVERY_STICKER: Final = "sticker"
DISCOVERY_MANUAL: Final = "manual"

# Device categories (from Dyson API)
DEVICE_CATEGORY_EC: Final = "ec"  # Environment Cleaner (fans with filters)
DEVICE_CATEGORY_LIGHT: Final = "light"  # Desk/floor lamps
DEVICE_CATEGORY_ROBOT: Final = "robot"  # Self-piloting devices
DEVICE_CATEGORY_VACUUM: Final = "vacuum"  # Suction cleaning devices
DEVICE_CATEGORY_FLRC: Final = "flrc"  # Floor cleaner devices
DEVICE_CATEGORY_WEARABLE: Final = "wearable"  # Wearable devices
DEVICE_CATEGORY_HC: Final = "hc"  # Hair care devices
DEVICE_CATEGORY_NOT_CONNECTED: Final = "notConnected"  # Skip these devices

# Supported device categories (skip unsupported ones)
SUPPORTED_DEVICE_CATEGORIES: Final = [
    DEVICE_CATEGORY_EC,
    DEVICE_CATEGORY_ROBOT,
    DEVICE_CATEGORY_VACUUM,
    DEVICE_CATEGORY_FLRC,
]

# Available device categories for manual device setup
AVAILABLE_DEVICE_CATEGORIES: Final = {
    DEVICE_CATEGORY_EC: "Environment Cleaner (air purifiers, fans with filters)",
    DEVICE_CATEGORY_ROBOT: "Robot Vacuum (self-piloting cleaning devices)",
    DEVICE_CATEGORY_VACUUM: "Vacuum Cleaner (suction cleaning devices)",
    DEVICE_CATEGORY_FLRC: "Floor Cleaner (mopping and floor cleaning devices)",
}

# Device capabilities
CAPABILITY_ADVANCE_OSCILLATION: Final = "AdvanceOscillationDay1"
CAPABILITY_SCHEDULING: Final = "Scheduling"
CAPABILITY_ENVIRONMENTAL_DATA: Final = "EnvironmentalData"
CAPABILITY_EXTENDED_AQ: Final = "ExtendedAQ"
CAPABILITY_CHANGE_WIFI: Final = "ChangeWifi"
CAPABILITY_HEATING: Final = "Heating"
CAPABILITY_FORMALDEHYDE: Final = "Formaldehyde"
CAPABILITY_HUMIDIFIER: Final = "Humidifier"

# Available capabilities for manual device setup
AVAILABLE_CAPABILITIES: Final = {
    CAPABILITY_ADVANCE_OSCILLATION: "Advanced Oscillation (precise angle control)",
    CAPABILITY_SCHEDULING: "Scheduling (timer and schedule controls)",
    CAPABILITY_ENVIRONMENTAL_DATA: "Environmental Data (meta-capability, no specific sensors created)",
    CAPABILITY_EXTENDED_AQ: "Extended Air Quality (PM2.5, PM10 sensors with continuous monitoring)",
    CAPABILITY_HEATING: "Heating (heat mode, temperature control, and temperature sensors)",
    CAPABILITY_FORMALDEHYDE: "Formaldehyde Detection (carbon filter, HCHO sensor, VOC/NO2 sensors, continuous monitoring)",
    CAPABILITY_HUMIDIFIER: "Humidifier (humidification controls and humidity sensors)",
}

# MQTT topics
MQTT_TOPIC_COMMAND: Final = "command"
MQTT_TOPIC_STATUS_CURRENT: Final = "status/current"
MQTT_TOPIC_STATUS_FAULT: Final = "status/fault"

# MQTT commands
MQTT_CMD_REQUEST_CURRENT_STATE: Final = "REQUEST-CURRENT-STATE"
MQTT_CMD_REQUEST_FAULTS: Final = "REQUEST-CURRENT-FAULTS"
MQTT_CMD_REQUEST_ENVIRONMENT: Final = "REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA"
MQTT_CMD_STATE_SET: Final = "STATE-SET"

# MQTT message types
MQTT_MSG_CURRENT_STATE: Final = "CURRENT-STATE"
MQTT_MSG_STATE_CHANGE: Final = "STATE-CHANGE"
MQTT_MSG_ENVIRONMENTAL_DATA: Final = "ENVIRONMENTAL-CURRENT-SENSOR-DATA"

# MQTT constants
MQTT_MODE_REASON: Final = "RAPP"  # Remote App
MQTT_PORT: Final = 1883

# Device state keys
STATE_KEY_POWER: Final = "fpwr"  # Fan power (ON/OFF)
STATE_KEY_FAN_STATE: Final = "fnst"  # Fan state (OFF/FAN)
STATE_KEY_FAN_SPEED: Final = "fnsp"  # Fan speed (0001-0010/AUTO)
STATE_KEY_AUTO_MODE: Final = "auto"  # Auto mode (ON/OFF)
STATE_KEY_NIGHT_MODE: Final = "nmod"  # Night mode (ON/OFF)
STATE_KEY_FAN_DIRECTION: Final = "fdir"  # Fan direction
STATE_KEY_HEPA_FILTER_LIFE: Final = "hflr"  # HEPA filter life
STATE_KEY_CARBON_FILTER_LIFE: Final = "cflr"  # Carbon filter life
STATE_KEY_HEPA_FILTER_TYPE: Final = "hflt"  # HEPA filter type
STATE_KEY_CARBON_FILTER_TYPE: Final = "cflt"  # Carbon filter type
STATE_KEY_SLEEP_TIMER: Final = "sltm"  # Sleep timer
STATE_KEY_CONTINUOUS_MONITORING: Final = "rhtm"  # Continuous monitoring

# Oscillation state keys
STATE_KEY_OSCILLATION_ON: Final = "oson"  # Oscillation on/off
STATE_KEY_OSCILLATION_UPPER: Final = "osau"  # Upper oscillation angle
STATE_KEY_OSCILLATION_LOWER: Final = "osal"  # Lower oscillation angle
STATE_KEY_OSCILLATION_CENTER: Final = "ancp"  # Angle center point

# Environmental data keys
STATE_KEY_PM25: Final = "pm25"  # PM2.5 particulate matter
STATE_KEY_PM10: Final = "pm10"  # PM10 particulate matter
STATE_KEY_P25R: Final = "p25r"  # P25R level
STATE_KEY_P10R: Final = "p10r"  # P10R level

# Filter values
FILTER_TYPE_GCOM: Final = "GCOM"  # Genuine Combi Filter
FILTER_TYPE_NONE: Final = "NONE"  # No filter installed
FILTER_VALUE_INVALID: Final = "INV"  # Invalid/no filter

# Connection status values
CONNECTION_STATUS_LOCAL: Final = "Local"
CONNECTION_STATUS_CLOUD: Final = "Cloud"
CONNECTION_STATUS_DISCONNECTED: Final = "Disconnected"

# Sleep timer limits (in minutes)
SLEEP_TIMER_MIN: Final = 15  # 15 minutes minimum
SLEEP_TIMER_MAX: Final = 540  # 9 hours maximum

# Fan speed limits
FAN_SPEED_MIN: Final = 1
FAN_SPEED_MAX: Final = 10
FAN_SPEED_AUTO: Final = "AUTO"

# Boolean values for MQTT
MQTT_ON: Final = "ON"
MQTT_OFF: Final = "OFF"

# mDNS service types
MDNS_SERVICE_DYSON: Final = "_dyson._mqtt._tcp.local."
MDNS_SERVICE_360EYE: Final = "_360eye._mqtt._tcp.local."

# Home Assistant platforms supported by this integration
PLATFORMS: Final = [
    "fan",
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "select",
    "switch",
    "vacuum",
    "climate",
]

# Service names
SERVICE_RESET_FILTER: Final = "reset_filter"
SERVICE_SET_SLEEP_TIMER: Final = "set_sleep_timer"
SERVICE_CANCEL_SLEEP_TIMER: Final = "cancel_sleep_timer"
SERVICE_SCHEDULE_OPERATION: Final = "schedule_operation"
SERVICE_SET_OSCILLATION_ANGLES: Final = "set_oscillation_angles"
SERVICE_FETCH_ACCOUNT_DATA: Final = "fetch_account_data"

# Event types
EVENT_DEVICE_FAULT: Final = "dyson_device_fault"

# Fault code translations
# Based on Dyson device fault codes - only non-OK values represent actual faults
FAULT_TRANSLATIONS: Final = {
    # Air quality sensor faults
    "aqs": {
        "FAIL": "Air quality sensor failure",
        "WARN": "Air quality sensor warning",
        "OFF": "Air quality sensor disabled",
    },
    # Filter faults
    "fltr": {
        "FAIL": "Filter failure - replace filter",
        "WARN": "Filter warning - low life remaining",
        "CHNG": "Filter needs replacement",
    },
    # HEPA filter faults
    "hflr": {
        "FAIL": "HEPA filter failure",
        "WARN": "HEPA filter warning - low life remaining",
        "CHNG": "HEPA filter needs replacement",
    },
    # Carbon filter faults
    "cflr": {
        "FAIL": "Carbon filter failure",
        "WARN": "Carbon filter warning - low life remaining",
        "CHNG": "Carbon filter needs replacement",
    },
    # Motor faults
    "mflr": {
        "FAIL": "Motor failure - device malfunction",
        "STLL": "Motor stall detected",
        "WRNG": "Motor warning",
    },
    # Temperature sensor faults
    "temp": {
        "FAIL": "Temperature sensor failure",
        "HIGH": "Temperature too high",
        "LOW": "Temperature too low",
    },
    # Humidity sensor faults
    "humi": {
        "FAIL": "Humidity sensor failure",
        "HIGH": "Humidity too high",
        "LOW": "Humidity too low",
    },
    # Power supply faults
    "pwr": {
        "FAIL": "Power supply failure",
        "VOLT": "Voltage fault detected",
        "CURR": "Current fault detected",
    },
    # Communication faults
    "wifi": {
        "FAIL": "WiFi connection failure",
        "WEAK": "WiFi signal weak",
        "DISC": "WiFi disconnected",
    },
    # General system faults
    "sys": {
        "FAIL": "System failure - contact support",
        "OVHT": "Device overheating",
        "LBAT": "Low battery warning",
    },
    # Brush faults (for vacuum models)
    "brsh": {
        "FAIL": "Brush failure - check for blockages",
        "STCK": "Brush stuck or blocked",
        "WORN": "Brush worn - needs replacement",
    },
    # Bin/dustbin faults
    "bin": {
        "FULL": "Dustbin full - please empty",
        "MISS": "Dustbin missing or not properly seated",
        "BLCK": "Dustbin blocked",
    },
}

# Device category to fault code mapping
# Only create fault sensors for fault types relevant to each device category
DEVICE_CATEGORY_FAULT_CODES: Final = {
    # Environment Cleaner (fans with filters) - air purifiers/fans
    DEVICE_CATEGORY_EC: [
        "mflr",  # Motor/fan
        "pwr",  # Power supply
        "wifi",  # WiFi connection
        "sys",  # System faults
    ],
    # Robot vacuum cleaners
    DEVICE_CATEGORY_ROBOT: [
        "mflr",  # Motor
        "pwr",  # Power supply
        "wifi",  # WiFi connection
        "sys",  # System faults
        "brsh",  # Brush system
        "bin",  # Dustbin
    ],
    # Regular vacuum cleaners
    DEVICE_CATEGORY_VACUUM: [
        "mflr",  # Motor
        "pwr",  # Power supply
        "wifi",  # WiFi connection
        "sys",  # System faults
        "brsh",  # Brush system
        "bin",  # Dustbin
    ],
    # Floor cleaner devices
    DEVICE_CATEGORY_FLRC: [
        "mflr",  # Motor
        "pwr",  # Power supply
        "wifi",  # WiFi connection
        "sys",  # System faults
        "brsh",  # Brush system
        "bin",  # Tank/reservoir
    ],
}

# Capability-based fault code filtering
# These faults only appear if the device has specific capabilities
CAPABILITY_FAULT_CODES: Final = {
    "ExtendedAQ": [
        "aqs",  # Air quality sensor
        "fltr",  # General filter
        "hflr",  # HEPA filter
    ],
    "Heating": [
        "temp",  # Temperature sensor
    ],
    # TODO: Identify formaldehyde capability name when we have a formaldehyde device
    # "Formaldehyde": [
    #     "cflr",  # Carbon filter
    # ],
    # TODO: Identify humidifier capability name when we have a humidifier device
    # "Humidifier": [
    #     "humi",  # Humidity sensor
    # ],
}
