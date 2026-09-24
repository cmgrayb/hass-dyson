"""Constants for the Dyson integration."""

from typing import Final

from homeassistant.components.vacuum import VacuumActivity

# Type alias for AQI ranges: (low, high, aqi_low, aqi_high, category)
# First two can be int or float depending on pollutant measurement units
AQIRange = tuple[float | int, float | int, int, int, str]

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
    DEVICE_CATEGORY_LIGHT,
]

# Available device categories for manual device setup
AVAILABLE_DEVICE_CATEGORIES: Final = {
    DEVICE_CATEGORY_EC: "Environment Cleaner (air purifiers, fans with filters)",
    DEVICE_CATEGORY_ROBOT: "Robot Vacuum (self-piloting cleaning devices)",
    DEVICE_CATEGORY_VACUUM: "Vacuum Cleaner (suction cleaning devices)",
    DEVICE_CATEGORY_FLRC: "Floor Cleaner (mopping and floor cleaning devices)",
    DEVICE_CATEGORY_LIGHT: "Light (BLE-only desk/floor lamps, e.g. Lightcycle Morph)",
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
CAPABILITY_FOCUS_MODE: Final = "FocusMode"

# Available capabilities for manual device setup
AVAILABLE_CAPABILITIES: Final = {
    CAPABILITY_ADVANCE_OSCILLATION_DAY0: "Advanced Oscillation Day 0 (specific oscillation pattern)",
    CAPABILITY_ADVANCE_OSCILLATION: "Advanced Oscillation Day 1 (wide angle control)",
    CAPABILITY_SCHEDULING: "Scheduling (timer and schedule controls)",
    CAPABILITY_ENVIRONMENTAL_DATA: "Environmental Data (temperature, humidity, PM2.5, PM10 sensors)",
    CAPABILITY_EXTENDED_AQ: "Extended Air Quality (CO2, NO2, VOC, HCHO sensors)",
    CAPABILITY_HEATING: "Heating (heat mode, temperature control, and temperature sensors)",
}

# AQI (Air Quality Index) Categories
AQI_CATEGORY_GOOD: Final = "Good"
AQI_CATEGORY_FAIR: Final = "Fair"
AQI_CATEGORY_POOR: Final = "Poor"
AQI_CATEGORY_VERY_POOR: Final = "Very Poor"
AQI_CATEGORY_EXTREMELY_POOR: Final = "Extremely Poor"
AQI_CATEGORY_SEVERE: Final = "Severe"

# AQI Range definitions based on Dyson PH05 guidelines (from vershart)
# Format: (low, high, aqi_low, aqi_high, category)
# PM2.5 ranges (μg/m³)
AQI_PM25_RANGES: Final[list[AQIRange]] = [
    (0, 35, 0, 50, AQI_CATEGORY_GOOD),
    (36, 53, 51, 100, AQI_CATEGORY_FAIR),
    (54, 70, 101, 150, AQI_CATEGORY_POOR),
    (71, 150, 151, 200, AQI_CATEGORY_VERY_POOR),
    (151, 250, 201, 300, AQI_CATEGORY_EXTREMELY_POOR),
    (251, 9999, 301, 500, AQI_CATEGORY_SEVERE),
]

# PM10 ranges (μg/m³)
AQI_PM10_RANGES: Final[list[AQIRange]] = [
    (0, 50, 0, 50, AQI_CATEGORY_GOOD),
    (51, 75, 51, 100, AQI_CATEGORY_FAIR),
    (76, 100, 101, 150, AQI_CATEGORY_POOR),
    (101, 350, 151, 200, AQI_CATEGORY_VERY_POOR),
    (351, 420, 201, 300, AQI_CATEGORY_EXTREMELY_POOR),
    (421, 9999, 301, 500, AQI_CATEGORY_SEVERE),
]

# HCHO (Formaldehyde) ranges (ppm)
AQI_HCHO_RANGES: Final[list[AQIRange]] = [
    (0.000, 0.099, 0, 50, AQI_CATEGORY_GOOD),
    (0.100, 0.299, 51, 100, AQI_CATEGORY_FAIR),
    (0.300, 0.499, 101, 150, AQI_CATEGORY_POOR),
    (0.500, 9999.0, 151, 500, AQI_CATEGORY_VERY_POOR),
]

# VOC ranges (raw device values) - Based on real-world testing by vershart (issue #236)
# Device reports raw values 0-100+; use raw value directly for AQI calculation
# For display: VOC(mg/m³) = device_value / 1000
# Example: device value 52 = Fair category (AQI ~75), displays as 0.052 mg/m³
AQI_VOC_RANGES: Final[list[AQIRange]] = [
    (0, 30, 0, 50, AQI_CATEGORY_GOOD),
    (31, 69, 51, 100, AQI_CATEGORY_FAIR),
    (70, 89, 101, 150, AQI_CATEGORY_POOR),
    (90, 250, 151, 200, AQI_CATEGORY_VERY_POOR),
    (251, 500, 201, 300, AQI_CATEGORY_EXTREMELY_POOR),
    (501, 9999, 301, 500, AQI_CATEGORY_SEVERE),
]

# NO2 ranges (ppb) - EPA AirNow guidelines
AQI_NO2_RANGES: Final[list[AQIRange]] = [
    (0, 53, 0, 50, AQI_CATEGORY_GOOD),
    (54, 100, 51, 100, AQI_CATEGORY_FAIR),
    (101, 360, 101, 150, AQI_CATEGORY_POOR),
    (361, 649, 151, 200, AQI_CATEGORY_VERY_POOR),
    (650, 1249, 201, 300, AQI_CATEGORY_EXTREMELY_POOR),
    (1250, 9999, 301, 500, AQI_CATEGORY_SEVERE),
]

# CO2 ranges (ppm) - EPA AirNow guidelines
AQI_CO2_RANGES: Final[list[AQIRange]] = [
    (0, 440, 0, 50, AQI_CATEGORY_GOOD),
    (441, 940, 51, 100, AQI_CATEGORY_FAIR),
    (941, 1240, 101, 150, AQI_CATEGORY_POOR),
    (1241, 1540, 151, 200, AQI_CATEGORY_VERY_POOR),
    (1541, 3050, 201, 300, AQI_CATEGORY_EXTREMELY_POOR),
    (3051, 9999, 301, 500, AQI_CATEGORY_SEVERE),
]

# Pollutant key mappings (newest to oldest)
# Each pollutant may have multiple keys across different device generations
POLLUTANT_KEYS: Final = {
    "pm25": ["p25r", "pm25", "pact"],
    "pm10": ["p10r", "pm10"],
    "voc": ["va10", "vact"],
    "no2": ["noxl"],
    "co2": ["co2r", "co2"],
    "hcho": ["hcho"],
}

_PM_SENSOR_UNAVAILABLE_STATES: Final = {
    "OFF": "inactive",
    "INIT": "initializing",
    "FAIL": "reporting a sensor fault",
    "NONE": "not reporting data",
}

_CO2_UNAVAILABLE_STATES: Final = {
    "OFF": "inactive",
    "INIT": "initializing",
    "FAIL": "reporting a sensor fault",
    "NONE": "not reporting data",
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
STATE_KEY_LEGACY_FILTER_LIFE: Final = "filf"  # Legacy filter life in hours
STATE_KEY_SLEEP_TIMER: Final = "sltm"  # Sleep timer
STATE_KEY_CONTINUOUS_MONITORING: Final = "rhtm"  # Continuous monitoring

# Oscillation state keys
STATE_KEY_OSCILLATION_ON: Final = "oson"  # Oscillation on/off
STATE_KEY_OSCILLATION_UPPER: Final = "osau"  # Upper oscillation angle
STATE_KEY_OSCILLATION_LOWER: Final = "osal"  # Lower oscillation angle
STATE_KEY_OSCILLATION_CENTER: Final = (
    "ancp"  # Angle custom preset (e.g. "CUST", "BRZE", or numeric center)
)

# Tilt oscillation state keys (vertical axis)
STATE_KEY_TILT_OSCILLATION_ON: Final = "oton"  # Tilt oscillation on/off (writable)
STATE_KEY_TILT_OSCILLATION_LOWER: Final = (
    "otal"  # Tilt lower angle, e.g. "0025" (writable)
)
STATE_KEY_TILT_OSCILLATION_UPPER: Final = (
    "otau"  # Tilt upper angle, e.g. "0025" (writable)
)
STATE_KEY_TILT_ANGLE_CONTROL: Final = (
    "anct"  # Tilt angle control preset: "CUST" or "BRZE" (writable)
)
STATE_KEY_TILT_OSCILLATION_STATUS: Final = (
    "otcs"  # Tilt oscillation control status (read-only)
)

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
STATE_KEY_FIND_FOLLOW: Final = "soon"  # Find+Follow on/off/scan command key
STATE_KEY_FIND_FOLLOW_STATUS: Final = "sost"  # Find+Follow engine status (read-only)

# Filter values
FILTER_TYPE_GCOM: Final = "GCOM"  # Genuine Combi Filter
FILTER_TYPE_NONE: Final = "NONE"  # No filter installed
FILTER_VALUE_INVALID: Final = "INV"  # Invalid/no filter

# Filter protocol limits
LEGACY_FILTER_LIFE_MAX_HOURS: Final = 4300

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
SERVICE_START_ZONE_CLEAN: Final = "start_zone_clean"
SERVICE_SET_ZONE_BEHAVIOUR: Final = "set_zone_behaviour"

# Event types
EVENT_DEVICE_FAULT: Final = "dyson_device_fault"
EVENT_BLE_STATE_CHANGE: Final = "dyson_ble_state_change"

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
        "FAIL": "Water tank not detected - please check that the tank is seated correctly",
        "OK": "Water tank detected",
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
ROBOT_STATE_FULL_CLEAN_INITIATED: Final = "FULL_CLEAN_INITIATED"
ROBOT_STATE_FULL_CLEAN_ABORTED: Final = "FULL_CLEAN_ABORTED"
ROBOT_STATE_FULL_CLEAN_NEEDS_CHARGE: Final = "FULL_CLEAN_NEEDS_CHARGE"
ROBOT_STATE_FULL_CLEAN_ABANDONED: Final = "FULL_CLEAN_ABANDONED"

# Mapping and Navigation
ROBOT_STATE_MAPPING_RUNNING: Final = "MAPPING_RUNNING"
ROBOT_STATE_MAPPING_PAUSED: Final = "MAPPING_PAUSED"
ROBOT_STATE_MAPPING_FINISHED: Final = "MAPPING_FINISHED"
ROBOT_STATE_MAPPING_INITIATED: Final = "MAPPING_INITIATED"
ROBOT_STATE_MAPPING_NEEDS_CHARGE: Final = "MAPPING_NEEDS_CHARGE"
ROBOT_STATE_MAPPING_ABORTED: Final = "MAPPING_ABORTED"

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
ROBOT_STATE_FAULT_ON_DOCK_CHARGED: Final = "FAULT_ON_DOCK_CHARGED"
ROBOT_STATE_FAULT_ON_DOCK_CHARGING: Final = "FAULT_ON_DOCK_CHARGING"
ROBOT_STATE_FAULT_RETURN_TO_DOCK: Final = "FAULT_RETURN_TO_DOCK"
ROBOT_STATE_FAULT_REPLACE_ON_DOCK: Final = "FAULT_REPLACE_ON_DOCK"
ROBOT_STATE_FAULT_CALL_HELPLINE: Final = "FAULT_CALL_HELPLINE"
ROBOT_STATE_FAULT_CONTACT_HELPLINE: Final = "FAULT_CONTACT_HELPLINE"
ROBOT_STATE_FAULT_GETTING_INFO: Final = "FAULT_GETTING_INFO"
ROBOT_STATE_FAULT_RUNNING_DIAGNOSTIC: Final = "FAULT_RUNNING_DIAGNOSTIC"

# Power state
ROBOT_STATE_MACHINE_OFF: Final = "MACHINE_OFF"

# Robot Vacuum Commands (MQTT)
ROBOT_CMD_START: Final = "START"
ROBOT_CMD_PAUSE: Final = "PAUSE"
ROBOT_CMD_RESUME: Final = "RESUME"
ROBOT_CMD_ABORT: Final = "ABORT"

ROBOT_CMD_REQUEST_STATE: Final = "REQUEST-CURRENT-STATE"

# Robot Vacuum MQTT Message Types
ROBOT_MSG_CURRENT_STATE: Final = "CURRENT-STATE"
ROBOT_MSG_STATE_CHANGE: Final = "STATE-CHANGE"
# Broadcast within ~1 minute of any persistent-map manifest change (zone
# edits in the MyDyson app, or the robot's own post-clean map update);
# payload is only {msg, time} — re-fetch the cloud metadata to see what.
ROBOT_MSG_MAP_MANIFEST_UPDATED: Final = "PERSISTENT-MAP-MANIFEST-UPDATED"

# Numeric fault codes the Spot+Scrub (RB05) reports in
# CURRENT-STATE.activeFaults. Names are Dyson's own, transcribed from the
# per-group pages under support.dyson.com.au -> Spot+Scrub Ai ->
# Troubleshooting -> Faults; the codes are on those sub-pages, not the
# index. Dyson gives several codes the same name. Codes it does not publish
# surface raw. Membership is not a fault signal - read nextActionRequired.
ROBOT_NUMERIC_FAULT_NAMES: Final = {
    "500": "LiDAR sensor obstructed",
    "501": "Wheels lifted",
    "502": "Battery is low",
    "503": "Robot's bin not detected",
    "504": "Gyroscopic sensor error",
    "507": "Unable to determine position",
    "508": "Unable to climb slope",
    "509": "Drop sensor obstructed",
    "510": "Collision sensor obstructed",
    "511": "Unable to return to dock",
    "513": "Robot stuck",
    "514": "Robot stuck",
    "516": "Battery temperature high",
    "518": "Battery is low",
    "521": "Dock's clean water tank not detected",
    "522": "Wet roller not detected",
    "560": "Side sweeper stuck",
    "561": "Camera obstructed",
    "562": "Wall follow sensor obstructed",
    "563": "Robot's bin not detected",
    "566": "Robot's dirty water tank not detected",
    "567": "Brush bar error",
    "568": "Left wheel stuck",
    "569": "Right wheel stuck",
    "570": "Brush bar error",
    "572": "Robot stuck",
    "581": "Dock's clean water tank empty",
    "582": "Dock's dirty water tank full",
    "583": "Dock's clean water tank not detected",
    "584": "Dock's dirty water tank not detected",
    "586": "Robot's dirty water tank full",
    "587": "Communication failure",
    "591": "Dock's bin full",
    "592": "Dock's filter error",
    "594": "Unable to empty robot's bin",
    "595": "Communication failure",
    "596": "Unable to empty robot's bin",
    "597": "Unable to empty robot's bin",
    "611": "Mapping failed",
    "612": "Mapping failed",
    "620": "Dock's cleaning solution empty",
    "627": "Something went wrong",
    "629": "Wet roller not detected",
    "630": "Wet roller stuck",
    "634": "Unable to return to dock",
    "636": "Robot stuck",
    "637": "Dock's clean water tank not detected",
    "639": "Wet roller not detected",
    "645": "Wet roller not detected",
    "646": "Wet roller error",
    "650": "Robot's dirty water tank not detected",
    "2000": "Dock's bin full",
    "2003": "Unable to start scheduled clean",
    "2007": "Mapping failed",
    "2012": "Unable to reach area",
    "2119": "Unable to start scheduled clean",
    "2123": "Dock's clean water pump error",
    "2124": "Dock's dirty water pump error",
    "2125": "Robot not charging",
    "2126": "Robot not charging",
    "2131": "Battery temperature too low",
    "2132": "Battery temperature too high",
    "2133": "Battery temperature too low",
}

# nextActionRequired value meaning "record it, nothing is wrong".
ROBOT_FAULT_ACTION_LOG_ONLY: Final = "LOG_ONLY"

# Robot fault subsystems, as keyed in the STATE-CHANGE top-level ``faults``
# dict ({SUBSYSTEM: {active, description-when-active}}). Distinct from the
# product-state CURRENT-FAULTS codes the generic fault sensors read.
ROBOT_FAULT_SUBSYSTEMS: Final = {
    "AIRWAYS": ("Airways", "mdi:weather-windy"),
    "BATTERY": ("Battery", "mdi:battery-alert"),
    "BRUSH_BAR_AND_TRACTION": ("Brush Bar & Traction", "mdi:robot-vacuum-alert"),
    "CHARGE_STATION": ("Charge Station", "mdi:ev-station"),
    "LIFT": ("Lift", "mdi:arrow-up-bold-box"),
    "LOST": ("Lost", "mdi:map-marker-question"),
    "OPTICS": ("Optics", "mdi:camera-off"),
}

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
    ROBOT_STATE_FULL_CLEAN_INITIATED: VacuumActivity.CLEANING,
    # Paused states
    ROBOT_STATE_FULL_CLEAN_PAUSED: VacuumActivity.PAUSED,
    ROBOT_STATE_MAPPING_PAUSED: VacuumActivity.PAUSED,
    # Docked states — the robot is ON the dock. The *_CHARGING pair are
    # mid-cycle recharges; .github/design/vacuums.md groups all five under
    # "Dock and Charging States".
    ROBOT_STATE_INACTIVE_CHARGED: VacuumActivity.DOCKED,
    ROBOT_STATE_INACTIVE_CHARGING: VacuumActivity.DOCKED,
    ROBOT_STATE_INACTIVE_DISCHARGING: VacuumActivity.DOCKED,
    ROBOT_STATE_FULL_CLEAN_CHARGING: VacuumActivity.DOCKED,
    ROBOT_STATE_MAPPING_CHARGING: VacuumActivity.DOCKED,
    # Returning states — en route to the dock, not on it yet
    ROBOT_STATE_FULL_CLEAN_FINISHED: VacuumActivity.RETURNING,
    ROBOT_STATE_FULL_CLEAN_ABORTED: VacuumActivity.RETURNING,
    ROBOT_STATE_FULL_CLEAN_NEEDS_CHARGE: VacuumActivity.RETURNING,
    ROBOT_STATE_MAPPING_NEEDS_CHARGE: VacuumActivity.RETURNING,
    ROBOT_STATE_MAPPING_ABORTED: VacuumActivity.RETURNING,
    # Mapping as idle (non-cleaning operation)
    ROBOT_STATE_MAPPING_RUNNING: VacuumActivity.IDLE,
    ROBOT_STATE_MAPPING_FINISHED: VacuumActivity.IDLE,
    ROBOT_STATE_MAPPING_INITIATED: VacuumActivity.IDLE,
    ROBOT_STATE_FULL_CLEAN_ABANDONED: VacuumActivity.IDLE,
    ROBOT_STATE_MACHINE_OFF: VacuumActivity.IDLE,
    # Error states
    ROBOT_STATE_FAULT_CRITICAL: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_USER_RECOVERABLE: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_LOST: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_ON_DOCK: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_ON_DOCK_CHARGED: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_ON_DOCK_CHARGING: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_RETURN_TO_DOCK: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_REPLACE_ON_DOCK: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_CALL_HELPLINE: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_CONTACT_HELPLINE: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_GETTING_INFO: VacuumActivity.ERROR,
    ROBOT_STATE_FAULT_RUNNING_DIAGNOSTIC: VacuumActivity.ERROR,
}

# Charging is orthogonal to the activity mapping above — a mid-clean recharge
# maps to RETURNING and an on-dock fault to ERROR, yet both draw charge.
ROBOT_STATES_CHARGING: Final = frozenset(
    {
        ROBOT_STATE_INACTIVE_CHARGING,
        ROBOT_STATE_FULL_CLEAN_CHARGING,
        ROBOT_STATE_MAPPING_CHARGING,
        ROBOT_STATE_FAULT_ON_DOCK_CHARGING,
    }
)

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
        "tnke",  # Water tank empty
        "tnkp",  # Water tank undetected
        "cldu",  # Unknown humidifier fault
        "etwd",  # Unknown humidifier fault
    ],
}

# ── BLE Light Constants ────────────────────────────────────────────────────────
# GATT service and characteristic UUIDs for Dyson BLE lights (Lightcycle Morph
# CD06).  UUID base: 2dd1xxxx-1c37-452d-8979-d1b4a787d0a4
# Source: reverse-engineered by S-Termi (discussion #334, authorized for inclusion).

# Primary GATT service
BLE_SERVICE_UUID: Final = "2dd10010-1c37-452d-8979-d1b4a787d0a4"

# Auth/messaging channel — write + notify; framed Dyson protocol messages
BLE_AUTH_CHAR_UUID: Final = "2dd10011-1c37-452d-8979-d1b4a787d0a4"

# RSSI proximity probe — 1-byte signed notify (used during fresh pairing only)
BLE_RSSI_CHAR_UUID: Final = "2dd10013-1c37-452d-8979-d1b4a787d0a4"

# Standard GAP device name — readable on every peripheral.  Used only as a
# link probe: the Dyson protocol is entirely write-without-response plus
# notify, so an acknowledged read is the one way to prove the ATT layer is
# alive in both directions.
BLE_GAP_DEVICE_NAME_CHAR_UUID: Final = "00002a00-0000-1000-8000-00805f9b34fb"

# Bonding must not stall a connection indefinitely; the lifecycle task can
# then never retry.  Generous enough for SMP over a proxy hop.
BLE_PAIR_TIMEOUT: Final = 20

# Light control characteristics
#
# NOTE: The Lightcycle Morph (CF06 / CD06) is a daylight-capable device.
# The Android MyDyson app (class a20.g, mod-connectivity_release) maps
# brightness to characteristic 11009 (BRIGHTNESS_OUTPUT_LUMENS_UUID) for
# daylight-capable devices, and to 11000 only for non-daylight devices.
# The CF06 firmware does NOT respond to writes on 11000.
BLE_BRIGHTNESS_UUID: Final = "2dd11000-1c37-452d-8979-d1b4a787d0a4"  # 1 byte, 0-100 % — non-daylight devices only
BLE_BRIGHTNESS_LUMENS_UUID: Final = "2dd11009-1c37-452d-8979-d1b4a787d0a4"  # uint16 LE, 100-1000 lm — daylight-capable (CF06)
BLE_COLOR_TEMP_UUID: Final = "2dd11001-1c37-452d-8979-d1b4a787d0a4"  # uint16 LE, Kelvin
BLE_POWER_UUID: Final = "2dd11005-1c37-452d-8979-d1b4a787d0a4"  # 1 byte: 0=off, 1=on

# Brightness lumens range (characteristic 11009, daylight-capable devices)
BLE_BRIGHTNESS_LUMENS_MIN: Final = 100  # minimum lamp brightness in lm
BLE_BRIGHTNESS_LUMENS_MAX: Final = 1000  # maximum lamp brightness in lm

# Runtime / diagnostic characteristics (partially decoded)
BLE_CHAR_11006_UUID: Final = (
    "2dd11006-1c37-452d-8979-d1b4a787d0a4"  # scheduled-light / auto-brightness flags
)
BLE_CHAR_11007_UUID: Final = "2dd11007-1c37-452d-8979-d1b4a787d0a4"  # movement sensor (MOVEMENT_SENSOR_UUID in Android)

# Motion detection characteristic — notify; non-zero payload = motion detected
BLE_MOTION_UUID: Final = "2dd11008-1c37-452d-8979-d1b4a787d0a4"

# Additional probe UUIDs read post-auth during device discovery
BLE_CHAR_11004_UUID: Final = "2dd11004-1c37-452d-8979-d1b4a787d0a4"
BLE_CHAR_10021_UUID: Final = "2dd10021-1c37-452d-8979-d1b4a787d0a4"

# Write-Attribute protocol (service 0020, characteristic 0021)
# Used to configure lamp operating modes on Dyson Lightcycle Morph (CF06).
# Protocol: write a 5-byte packet to characteristic 0021 —
#   bytes 0-1 = attribute ID (little-endian)
#   bytes 2-3 = length of value field (uint16 LE)
#   bytes 4..  = value
#
# DAYLIGHT_MODE (attribute 0x2013 = {0x13, 0x20}):
#   When enabled the lamp controls its own brightness/colour-temperature via its
#   daylight algorithm and silently ignores BLE writes to char 11009/11001.
#   Home Assistant must disable this mode before issuing manual brightness or
#   colour-temperature commands (source: q90.C30554a / ga0.C15075x2).
BLE_WRITE_ATTR_CHAR_UUID: Final = "2dd10021-1c37-452d-8979-d1b4a787d0a4"
# Packet: DAYLIGHT_MODE attribute = false  →  lamp enters manual control mode
BLE_DAYLIGHT_MODE_DISABLE_PAYLOAD: Final = bytes([0x13, 0x20, 0x01, 0x00, 0x00])
# Packet: DAYLIGHT_MODE attribute = true  →  lamp enters daylight/auto mode
BLE_DAYLIGHT_MODE_ENABLE_PAYLOAD: Final = bytes([0x13, 0x20, 0x01, 0x00, 0x01])

# Dyson device capability strings for daylight-capable BLE lights (CF06/CD06).
# Used to gate the daylight-mode switch entity.
BLE_CAPABILITY_DAYLIGHT: Final = "Daylight"
BLE_CAPABILITY_PERSONAL_DAYLIGHT: Final = "PersonalDaylight"

# BLE message type constants (logical message type byte on char 11011)
# Fresh pairing flow (requires physical button press — one-time operation)
BLE_MSG_TYPE_AUTH_PAYLOAD_A: Final = 0x01  # → lamp: PayloadA (apiAuthCode)
BLE_MSG_TYPE_AUTH_PAYLOAD_B: Final = 0x02  # ← lamp: PayloadB
BLE_MSG_TYPE_AUTH_PAYLOAD_3: Final = 0x03  # → lamp: Payload3 (final verify)
BLE_MSG_TYPE_HELLO: Final = 0x04  # → lamp: start fresh pairing
BLE_MSG_TYPE_UNIQUE_PRODUCT_CODE: Final = 0x05  # ← lamp: 32-byte unique code
BLE_MSG_TYPE_SEND_API_RAN_NUM: Final = 0x09  # → lamp: apiRanNum nonce
BLE_MSG_TYPE_SUBSCRIBE_RSSI: Final = 0x0C  # → lamp: RSSI proximity probe
BLE_MSG_TYPE_USER_CONFIRMED: Final = 0x0D  # ← lamp: Flash button pressed

# LTK re-auth flow (silent reconnect — no button, no cloud call)
BLE_MSG_TYPE_REAUTH_PAYLOAD_A: Final = 0x06  # → lamp: 82-byte challenge
BLE_MSG_TYPE_REAUTH_PAYLOAD_B: Final = 0x07  # ← lamp: challenge response
BLE_MSG_TYPE_REAUTH_PAYLOAD_C: Final = 0x08  # → lamp: 66-byte reply

# Product info exchange
BLE_MSG_TYPE_REQUEST_PRODUCT_INFO: Final = 0x0A  # → lamp: request info
BLE_MSG_TYPE_PRODUCT_INFO: Final = 0x0B  # ← lamp: firmware/hardware info

# Shared
BLE_MSG_TYPE_CONNECTION_ESTABLISHED: Final = 0x26  # ← lamp: auth complete

# BLE crypto constants
# HKDF info string used to derive the AES key from the LTK
BLE_HKDF_INFO: Final = b"USER_AUTH_AES\x00\x00\x00"

# Hardcoded Dyson LTK auth fallback code (observed across multiple accounts)
BLE_LTK_FALLBACK_CODE: Final = "80541406"

# BLE color temperature limits (Kelvin)
BLE_MIN_KELVIN: Final = 2700  # warmest (≈ 370 mired)
BLE_MAX_KELVIN: Final = 6500  # coolest (≈ 154 mired)

# BLE configuration keys (stored in config entry data)
CONF_BLE_MAC: Final = "ble_mac"  # BLE MAC address (e.g. AA:BB:CC:DD:EE:FF)
CONF_LTK: Final = "ltk"  # Long Term Key hex string (obtained via cloud pairing)
CONF_BLE_PROXY: Final = "ble_proxy"  # Optional: pinned Bluetooth proxy host

# Dyson reports and accepts temperatures as Kelvin x 10, e.g. "2890" = 289.0 K.
ZERO_CELSIUS_IN_KELVIN: Final = 273.15

# ── BLE Floor-cleaner (floorcare / LEC vacuum, e.g. V16 Piston Animal) ──────
# Device kind marker stored in BLE config entries so entry setup can route
# vacuum entries to the attribute-protocol stack instead of the light stack.
CONF_BLE_DEVICE_KIND: Final = "ble_device_kind"
BLE_DEVICE_KIND_LIGHT: Final = "light"
BLE_DEVICE_KIND_VACUUM: Final = "vacuum"

# Messaging-channel message types (service 0020, characteristic 0021).
# Attribute protocol: read / write / push-subscribe / push / subscribe-ack.
BLE_MSG_TYPE_READ_ATTRIBUTE_REQUEST: Final = 0x90
BLE_MSG_TYPE_READ_ATTRIBUTE_RESPONSE: Final = 0x91
BLE_MSG_TYPE_WRITE_ATTRIBUTE_REQUEST: Final = 0x93
# Write-status response from the machine: attrId(2) + writeStatus(1).
BLE_MSG_TYPE_WRITE_ATTRIBUTE_RESPONSE: Final = 0x94
BLE_MSG_TYPE_PUSH_ATTRIBUTE_REQUEST: Final = 0x96
BLE_MSG_TYPE_PUSH_ATTRIBUTE: Final = 0x97
BLE_MSG_TYPE_PUSH_ATTRIBUTE_ACK: Final = 0x98
BLE_MSG_TYPE_APP_ACTIVE_STATUS: Final = 0x30

# AppActiveStatus payload values — the app sends these to tell the machine
# whether a foreground client is attached.  Always send ACTIVE on connect and
# INACTIVE before disconnecting, or the machine can ignore its own buttons
# for several seconds after the session.
BLE_APP_STATUS_FOREGROUND_ACTIVE: Final = 0x00
BLE_APP_STATUS_INACTIVE: Final = 0x01
BLE_PUSH_STATUS_ACTIVE: Final = 0x00
BLE_PUSH_STATUS_INACTIVE: Final = 0x01

# Pacing — the vacuum's BLE stack reboots when flooded with back-to-back
# writes (~10 s of ignored button presses).  These intervals/limits are
# deliberately inside the envelope the MyDyson app itself uses.
BLE_ATTR_READ_INTERVAL: Final = 0.5
BLE_ATTR_SUBSCRIBE_INTERVAL: Final = 0.4
BLE_ATTR_ACK_TIMEOUT: Final = 2.0
BLE_ATTR_MAX_CONSECUTIVE_ERRORS: Final = 2

# Connection lifecycle pacing for the vacuum coordinator.
BLE_VACUUM_KEEPALIVE_INTERVAL: Final = 20.0
BLE_VACUUM_RECONNECT_DELAYS: Final = [5, 15, 30, 60]

# How often the BLE vacuum coordinator asks the Dyson cloud whether newer
# firmware exists.  The machine itself has no internet and cannot answer this,
# but firmware releases are rare, so once every 12 hours is plenty and keeps
# the load off Dyson's API.
BLE_VACUUM_CLOUD_FIRMWARE_INTERVAL: Final = 12 * 60 * 60.0

# Attribute registry for cat6 connected floorcare (V16 et al.).
# attr id bytes (wire order) -> (state key, human label, decoder hint)
# decoder hint is either "int", "bool", "raw", or a dict mapping value->label.
# Wire value -> option slug.  These are entity *states*, so they have to match
# Home Assistant's `[a-z0-9-_]+` rule for translation keys (hassfest enforces
# it); the display names live in translations/en.json under the same slugs.
_BLE_LANG_OPTIONS: Final = {
    0: "english",
    1: "korean",
    2: "spanish",
    3: "french",
    4: "japanese",
    5: "simplified_chinese",
    6: "traditional_chinese",
    7: "german",
    8: "italian",
    9: "dutch",
    10: "russian",
    11: "arabic",
    12: "czech",
    13: "danish",
    14: "greek",
    15: "finnish",
    16: "hebrew",
    17: "croatian",
    18: "hungarian",
    19: "lithuanian",
    20: "norwegian",
    21: "polish",
    22: "portuguese",
    23: "slovenian",
    24: "swedish",
    25: "thai",
    26: "turkish",
    27: "spanish_us",
    28: "french_canada",
    29: "portuguese_brazil",
}

BLE_VACUUM_ATTR_POWER_MODE: Final = bytes((0x00, 0x40))
BLE_VACUUM_ATTR_BLOCKAGE: Final = bytes((0x00, 0x42))
BLE_VACUUM_ATTR_BATTERY_TEMPERATURE: Final = bytes((0x05, 0x42))
BLE_VACUUM_ATTR_FILTER_PRESENT: Final = bytes((0x01, 0x42))
BLE_VACUUM_ATTR_FILTER_WASH: Final = bytes((0x02, 0x42))
BLE_VACUUM_ATTR_SYSTEM_ERROR: Final = bytes((0x09, 0x42))
BLE_VACUUM_ATTR_CHARGE_REQUIRED: Final = bytes((0x0A, 0x42))
BLE_VACUUM_ATTR_BATTERY_LEVEL: Final = bytes((0x02, 0x40))
BLE_VACUUM_ATTR_ACTIVELY_CHARGING: Final = bytes((0x03, 0x40))
BLE_VACUUM_ATTR_CHARGER_PRESENT: Final = bytes((0x04, 0x40))
BLE_VACUUM_ATTR_UI_LANGUAGE: Final = bytes((0x02, 0x41))
BLE_VACUUM_ATTR_BATTERY_CARE_SETTING: Final = bytes((0x08, 0x41))
BLE_VACUUM_ATTR_BATTERY_AUTHENTICITY: Final = bytes((0x07, 0x42))
BLE_VACUUM_ATTR_TASK_DETECTION: Final = bytes((0x07, 0x41))
BLE_VACUUM_ATTR_DUST_ILLUMINATION: Final = bytes((0x0A, 0x40))
BLE_VACUUM_ATTR_BRUSH_BAR_SPEED: Final = bytes((0x0B, 0x40))
BLE_VACUUM_ATTR_BRUSH_BAR_TYPE: Final = bytes((0x0C, 0x40))
BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE: Final = bytes((0x07, 0x40))
# 0x0243 is a 32-bit little-endian capability bitmask, not a scalar state.
# The MyDyson app (iq/b.java) widens the payload to 4 bytes LE and mask-tests
# it against iq.c {AUTO = 0b111, NOT_AUTO = fallback}, reducing the whole
# attribute to the boolean it calls "dustIlluminationAutoState": whether the
# AUTO dust-illumination option is available with the currently attached head.
BLE_VACUUM_ATTR_DUST_ILLUMINATION_AUTO: Final = bytes((0x02, 0x43))
BLE_VACUUM_LDI_AUTO_MASK: Final = 0b111

BLE_VACUUM_POWER_MODES: Final = {0: "eco", 1: "med", 2: "auto", 3: "boost"}
BLE_VACUUM_BLOCKAGE_STATES: Final = {
    0: "not_blocked",
    1: "inlet_blocked",
    2: "inlet_blocked_and_error",
    3: "outlet_blocked_and_error",
}
BLE_VACUUM_BATTERY_TEMPERATURES: Final = {0: "ok", 1: "cold", 2: "hot"}
BLE_VACUUM_FILTER_PRESENT_STATES: Final = {
    0: "filter_present",
    1: "filter_not_present",
    2: "unknown",
}
BLE_VACUUM_FILTER_WASH_STATES: Final = {0: "filter_ok", 1: "filter_needs_cleaning"}
BLE_VACUUM_CHARGE_REQUIRED_STATES: Final = {
    0: "no_charge_required",
    1: "place_on_charge",
}
BLE_VACUUM_LANGUAGES: Final = _BLE_LANG_OPTIONS
BLE_VACUUM_BATTERY_AUTHENTICITY_STATES: Final = {0: "dyson", 1: "non_dyson"}
BLE_VACUUM_DUST_ILLUMINATION_MODES: Final = {0: "off", 1: "on", 2: "auto"}
# Wire values per the MyDyson app's BrushBarSpeed enum. "fixed" is only a
# sentinel for "head has no variable speed", never a live value on the wire.
BLE_VACUUM_BRUSH_BAR_SPEEDS: Final = {0: "low", 1: "high", 2: "auto"}
# Wire values per the MyDyson app's brush-bar-type enum; "none attached" is
# sent as 0xFF (i.e. -1).
BLE_VACUUM_BRUSH_BAR_TYPES: Final = {
    1: "erp_768",
    2: "row_768",
    255: "none_attached",
}
BLE_VACUUM_SESSION_STATES: Final = {0: "inactive", 1: "active"}

# Full read/subscribe list for the floorcare attribute manager.
# attr_id -> (state key, {value: label} | "int" | "bool")
BLE_VACUUM_ATTRIBUTES: Final = {
    BLE_VACUUM_ATTR_POWER_MODE: ("power_mode", BLE_VACUUM_POWER_MODES),
    BLE_VACUUM_ATTR_BLOCKAGE: ("blockage", BLE_VACUUM_BLOCKAGE_STATES),
    BLE_VACUUM_ATTR_BATTERY_TEMPERATURE: (
        "battery_temperature",
        BLE_VACUUM_BATTERY_TEMPERATURES,
    ),
    BLE_VACUUM_ATTR_FILTER_PRESENT: (
        "filter_present",
        BLE_VACUUM_FILTER_PRESENT_STATES,
    ),
    BLE_VACUUM_ATTR_FILTER_WASH: ("filter_wash", BLE_VACUUM_FILTER_WASH_STATES),
    BLE_VACUUM_ATTR_SYSTEM_ERROR: ("system_error", "bool"),
    BLE_VACUUM_ATTR_CHARGE_REQUIRED: (
        "charge_required",
        BLE_VACUUM_CHARGE_REQUIRED_STATES,
    ),
    BLE_VACUUM_ATTR_BATTERY_LEVEL: ("battery_level", "int"),
    BLE_VACUUM_ATTR_ACTIVELY_CHARGING: ("actively_charging", "bool"),
    BLE_VACUUM_ATTR_CHARGER_PRESENT: ("charger_present", "bool"),
    BLE_VACUUM_ATTR_UI_LANGUAGE: ("ui_language", BLE_VACUUM_LANGUAGES),
    BLE_VACUUM_ATTR_BATTERY_CARE_SETTING: ("battery_care_setting", "bool"),
    BLE_VACUUM_ATTR_BATTERY_AUTHENTICITY: (
        "battery_authenticity",
        BLE_VACUUM_BATTERY_AUTHENTICITY_STATES,
    ),
    BLE_VACUUM_ATTR_TASK_DETECTION: ("task_detection", "bool"),
    BLE_VACUUM_ATTR_DUST_ILLUMINATION: (
        "dust_illumination",
        BLE_VACUUM_DUST_ILLUMINATION_MODES,
    ),
    BLE_VACUUM_ATTR_BRUSH_BAR_SPEED: ("brush_bar_speed", BLE_VACUUM_BRUSH_BAR_SPEEDS),
    BLE_VACUUM_ATTR_BRUSH_BAR_TYPE: ("brush_bar_type", BLE_VACUUM_BRUSH_BAR_TYPES),
    BLE_VACUUM_ATTR_CLEANING_SESSION_ACTIVE: (
        "session_active",
        BLE_VACUUM_SESSION_STATES,
    ),
    BLE_VACUUM_ATTR_DUST_ILLUMINATION_AUTO: ("dust_illumination_auto", "ldi_auto"),
}


def decikelvin_to_celsius(decikelvin: float) -> float:
    """Convert a Dyson Kelvin x 10 temperature to degrees Celsius."""
    return decikelvin / 10 - ZERO_CELSIUS_IN_KELVIN


def celsius_to_decikelvin(celsius: float) -> int:
    """Convert degrees Celsius to the Dyson Kelvin x 10 representation.

    Rounds to the nearest step the device can hold. A whole number of degrees
    Celsius never lands exactly on a tenth of a Kelvin (16 C is 2891.5), so the
    value has to be rounded either way; truncating would always bias the stored
    setpoint downwards.
    """
    return round((celsius + ZERO_CELSIUS_IN_KELVIN) * 10)
