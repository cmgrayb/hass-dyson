"""Constants for the Dyson integration."""

from typing import Final

from homeassistant.components.vacuum import VacuumActivity

# Integration domain
DOMAIN: Final = "hass_dyson"

# Default values
DEFAULT_CLOUD_POLLING_INTERVAL: Final = 60  # 1 minute in seconds
# 1 minute for connectivity checks only (devices send natural STATE-CHANGE messages)
DEFAULT_DEVICE_POLLING_INTERVAL: Final = 60
DEFAULT_TIMEOUT: Final = 10  # 10 seconds for network operations
DEFAULT_POLL_FOR_DEVICES: Final = True  # Default to enabled for backward compatibility
DEFAULT_AUTO_ADD_DEVICES: Final = True  # Default to enabled for backward compatibility

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

# Cloud account configuration keys
CONF_POLL_FOR_DEVICES: Final = "poll_for_devices"
CONF_AUTO_ADD_DEVICES: Final = "auto_add_devices"
CONF_COUNTRY: Final = "country"
CONF_CULTURE: Final = "culture"

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


# Exceptions
class UnsupportedDeviceError(Exception):
    """Exception raised when device does not support required features (e.g., MQTT)."""

    pass


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
CAPABILITY_ADVANCE_OSCILLATION_DAY0: Final = "AdvanceOscillationDay0"
CAPABILITY_ADVANCE_OSCILLATION: Final = "AdvanceOscillationDay1"
CAPABILITY_SCHEDULING: Final = "Scheduling"
CAPABILITY_ENVIRONMENTAL_DATA: Final = "EnvironmentalData"
CAPABILITY_EXTENDED_AQ: Final = "ExtendedAQ"
CAPABILITY_CHANGE_WIFI: Final = "ChangeWifi"
CAPABILITY_HEATING: Final = "Heating"
CAPABILITY_FORMALDEHYDE: Final = "Formaldehyde"
CAPABILITY_VOC: Final = "VOC"
CAPABILITY_HUMIDIFIER: Final = "Humidifier"

# Available capabilities for manual device setup
AVAILABLE_CAPABILITIES: Final = {
    CAPABILITY_ADVANCE_OSCILLATION_DAY0: "Advanced Oscillation Day 0 (specific oscillation pattern)",
    CAPABILITY_ADVANCE_OSCILLATION: "Advanced Oscillation Day 1 (wide angle control)",
    CAPABILITY_SCHEDULING: "Scheduling (timer and schedule controls)",
    CAPABILITY_ENVIRONMENTAL_DATA: "Environmental Data (temperature, humidity, PM2.5, PM10 sensors)",
    CAPABILITY_EXTENDED_AQ: "Extended Air Quality (CO2, NO2, VOC, HCHO sensors)",
    CAPABILITY_HEATING: "Heating (heat mode, temperature control, and temperature sensors)",
    CAPABILITY_VOC: "VOC/NO2 Detection (VOC/NO2 sensors)",
    CAPABILITY_FORMALDEHYDE: "Formaldehyde Detection (carbon filter, HCHO sensor)",
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
STATE_KEY_OSCILLATION_CENTER: Final = "ancp"  # Angle control preset

# Humidifier state keys
STATE_KEY_HUMIDITY_ENABLED: Final = "hume"  # Humidity mode (HUMD/OFF)
STATE_KEY_HUMIDITY_AUTO: Final = "haut"  # Humidity auto mode (ON/OFF)
STATE_KEY_HUMIDITY_TARGET: Final = "humt"  # Target humidity (0030-0050)
STATE_KEY_HUMIDITY_CURRENT: Final = "humi"  # Current humidity sensor reading
STATE_KEY_WATER_HARDNESS: Final = "wath"  # Water hardness (2025/1350/0675)
STATE_KEY_CLEAN_TIME_REMAINING: Final = "cltr"  # Clean time remaining (hours)
STATE_KEY_CLEANING_CYCLE_REMAINING: Final = "cdrr"  # Cleaning cycle remaining (minutes)

# Environmental data keys
STATE_KEY_PM25: Final = "pm25"  # PM2.5 particulate matter
STATE_KEY_PM10: Final = "pm10"  # PM10 particulate matter
STATE_KEY_P25R: Final = "p25r"  # P25R level
STATE_KEY_P10R: Final = "p10r"  # P10R level
STATE_KEY_VOC: Final = "va10"  # VOC (Volatile Organic Compounds)
STATE_KEY_NO2: Final = "noxl"  # NO2 (Nitrogen Dioxide)
STATE_KEY_FORMALDEHYDE: Final = "hcho"  # Formaldehyde raw value
STATE_KEY_FORMALDEHYDE_DISPLAY: Final = "hchr"  # Formaldehyde display value

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
SERVICE_REFRESH_ACCOUNT_DATA: Final = "refresh_account_data"
SERVICE_GET_CLOUD_DEVICES: Final = "get_cloud_devices"

# Event types
EVENT_DEVICE_FAULT: Final = "dyson_device_fault"

# Fault code translations
# Based on Dyson device fault codes - only non-OK values represent actual faults
# To do: investigate moving these to localization files for translation support
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
    # Humidifier-specific faults
    "tnke": {
        "FAIL": "Water tank empty - please refill",
        "OK": "Water tank level normal",
    },
    "tnkp": {
        "FAIL": "Water tank problem - check placement",
        "OK": "Water tank status normal",
    },
    "cldu": {
        "FAIL": "Humidifier cleaning required",
        "OK": "Humidifier clean status normal",
    },
    "etwd": {
        "FAIL": "Humidifier maintenance required",
        "OK": "Humidifier maintenance status normal",
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

# Robot Vacuum Constants
# =====================

# Robot Vacuum States (from design documentation)
# Primary Operating Modes
ROBOT_STATE_FULL_CLEAN_RUNNING: Final = "FULL_CLEAN_RUNNING"
ROBOT_STATE_FULL_CLEAN_PAUSED: Final = "FULL_CLEAN_PAUSED"
ROBOT_STATE_FULL_CLEAN_FINISHED: Final = "FULL_CLEAN_FINISHED"
ROBOT_STATE_FULL_CLEAN_DISCOVERING: Final = "FULL_CLEAN_DISCOVERING"
ROBOT_STATE_FULL_CLEAN_TRAVERSING: Final = "FULL_CLEAN_TRAVERSING"

# Mapping and Navigation
ROBOT_STATE_MAPPING_RUNNING: Final = "MAPPING_RUNNING"
ROBOT_STATE_MAPPING_PAUSED: Final = "MAPPING_PAUSED"
ROBOT_STATE_MAPPING_FINISHED: Final = "MAPPING_FINISHED"

# Dock and Charging States
ROBOT_STATE_INACTIVE_CHARGED: Final = "INACTIVE_CHARGED"
ROBOT_STATE_INACTIVE_CHARGING: Final = "INACTIVE_CHARGING"
ROBOT_STATE_INACTIVE_DISCHARGING: Final = "INACTIVE_DISCHARGING"
ROBOT_STATE_FULL_CLEAN_CHARGING: Final = "FULL_CLEAN_CHARGING"
ROBOT_STATE_MAPPING_CHARGING: Final = "MAPPING_CHARGING"

# Error and Fault Conditions
ROBOT_STATE_FAULT_CRITICAL: Final = "FAULT_CRITICAL"
ROBOT_STATE_FAULT_USER_RECOVERABLE: Final = "FAULT_USER_RECOVERABLE"
ROBOT_STATE_FAULT_LOST: Final = "FAULT_LOST"
ROBOT_STATE_FAULT_ON_DOCK: Final = "FAULT_ON_DOCK"
ROBOT_STATE_FAULT_RETURN_TO_DOCK: Final = "FAULT_RETURN_TO_DOCK"

# Robot Vacuum Commands (MQTT)
ROBOT_CMD_PAUSE: Final = "PAUSE"
ROBOT_CMD_RESUME: Final = "RESUME"
ROBOT_CMD_ABORT: Final = "ABORT"
ROBOT_CMD_REQUEST_STATE: Final = "REQUEST-CURRENT-STATE"

# Robot Vacuum MQTT Message Types
ROBOT_MSG_CURRENT_STATE: Final = "CURRENT-STATE"
ROBOT_MSG_STATE_CHANGE: Final = "STATE-CHANGE"

# Robot Vacuum Cleaning Types
ROBOT_CLEAN_TYPE_IMMEDIATE: Final = "immediate"
ROBOT_CLEAN_TYPE_MANUAL: Final = "manual"
ROBOT_CLEAN_TYPE_SCHEDULED: Final = "scheduled"

# Robot Vacuum Area Modes
ROBOT_AREA_MODE_GLOBAL: Final = "global"
ROBOT_AREA_MODE_ZONE_CONFIGURED: Final = "zoneConfigured"

# Robot Vacuum Power Levels (capability-based)
# 360 Eye Model (halfPower/fullPower capability)
ROBOT_POWER_360_EYE_HALF: Final = "halfPower"
ROBOT_POWER_360_EYE_FULL: Final = "fullPower"

# 360 Heurist Model (1/2/3 levels capability)
ROBOT_POWER_HEURIST_QUIET: Final = "1"
ROBOT_POWER_HEURIST_HIGH: Final = "2"
ROBOT_POWER_HEURIST_MAX: Final = "3"

# 360 Vis Nav Model (1/2/3/4 levels capability)
ROBOT_POWER_VIS_NAV_AUTO: Final = "1"
ROBOT_POWER_VIS_NAV_QUICK: Final = "2"
ROBOT_POWER_VIS_NAV_QUIET: Final = "3"
ROBOT_POWER_VIS_NAV_BOOST: Final = "4"

# Robot Vacuum Power Level Options (for select entities)
ROBOT_POWER_OPTIONS_360_EYE: Final = {
    ROBOT_POWER_360_EYE_HALF: "Quiet (Half Power)",
    ROBOT_POWER_360_EYE_FULL: "Deep Clean (Full Power)",
}

ROBOT_POWER_OPTIONS_HEURIST: Final = {
    ROBOT_POWER_HEURIST_QUIET: "Quiet Mode",
    ROBOT_POWER_HEURIST_HIGH: "High Mode",
    ROBOT_POWER_HEURIST_MAX: "Maximum Mode",
}

ROBOT_POWER_OPTIONS_VIS_NAV: Final = {
    ROBOT_POWER_VIS_NAV_AUTO: "Auto Mode",
    ROBOT_POWER_VIS_NAV_QUICK: "Quick Mode",
    ROBOT_POWER_VIS_NAV_QUIET: "Quiet Mode",
    ROBOT_POWER_VIS_NAV_BOOST: "Boost Mode",
}

ROBOT_STATE_TO_HA_STATE: Final = {
    # Active cleaning states
    ROBOT_STATE_FULL_CLEAN_RUNNING: VacuumActivity.CLEANING,
    ROBOT_STATE_FULL_CLEAN_DISCOVERING: VacuumActivity.CLEANING,
    ROBOT_STATE_FULL_CLEAN_TRAVERSING: VacuumActivity.CLEANING,
    # Paused states
    ROBOT_STATE_FULL_CLEAN_PAUSED: VacuumActivity.PAUSED,
    ROBOT_STATE_MAPPING_PAUSED: VacuumActivity.PAUSED,
    # Docked states
    ROBOT_STATE_INACTIVE_CHARGED: VacuumActivity.DOCKED,
    ROBOT_STATE_INACTIVE_CHARGING: VacuumActivity.DOCKED,
    ROBOT_STATE_INACTIVE_DISCHARGING: VacuumActivity.DOCKED,
    # Returning states
    ROBOT_STATE_FULL_CLEAN_FINISHED: VacuumActivity.RETURNING,
    ROBOT_STATE_FULL_CLEAN_CHARGING: VacuumActivity.RETURNING,
    ROBOT_STATE_MAPPING_CHARGING: VacuumActivity.RETURNING,
    # Mapping as idle (non-cleaning operation)
    ROBOT_STATE_MAPPING_RUNNING: VacuumActivity.IDLE,
    ROBOT_STATE_MAPPING_FINISHED: VacuumActivity.IDLE,
    # Error states
    ROBOT_STATE_FAULT_CRITICAL: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_USER_RECOVERABLE: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_LOST: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_ON_DOCK: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_RETURN_TO_DOCK: VacuumActivity.ERROR,
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
    "VOC": [
        "aqs",  # Air quality sensor (VOC/NO2 sensors)
    ],
    "Formaldehyde": [
        "cflr",  # Carbon filter
        "aqs",  # Air quality sensor
    ],
    "Humidifier": [
        "humi",  # Humidity sensor
        "fltr",  # General filter (covers humidifier filter)
        "tnke",  # Tank empty
        "tnkp",  # Tank problem
        "cldu",  # Unknown humidifier fault
        "etwd",  # Unknown humidifier fault
    ],
}
