# Discovery

This file documents the discovery process for Dyson devices

## Cloud-based Discovery

Cloud-based discovery should be the default method for determining new Dyson devices, as this is the newest method given by the manufacturer and least prone to lose support as a result.
Discovery of new devices is performed through methods found in libdyson-rest.
Devices with a DeviceCategory of notConnected should be skipped.
Polling should occur approximately every five minutes by default for new devices.
Upon identifying a new device in a cloud account, the device should optionally automatically add itself to Home Assistant without any further interaction by the user, as all necessary information should already be in the device information returned.
Examples of the information available from the API through libdyson-rest may be found in the .local folder.

## mDNS discovery

mDNS discovery (Zeroconf, paho-client-mqtt) may or may not correctly identify a device on the network.
Newer models do not consistently include their variant as part of the advertisement, do not include connection credentials, and are generally only useful for local DNS hostname and IP information in the case that the fan reports different information to the API.  mDNS-based discovery should only be used as a fallback for host connection determination in the case that the hostname or IP returned to the API is different.  When falling back to mDNS, search for an advertisement with a format of [model with or without variant]_[serial number]._dyson._mqtt._tcp to match the cloud device to the local device.  This method appears to be particularly useful for devices returning "ec" (environment cleaner) in the DeviceCategory in the API, which represent devices with a fan and filter.

Some devices also broadcast on [model with or without variant]_[serial number]._360eye._mqtt._tcp, particularly robotic vacuums.  In the case that the device returns "robot", "vacuum" or "flrc" in the DeviceCategory (index [device][category] of the json response), this additional advertisement should be checked for.

## Sticker and "WiFi based" discovery

Sticker-based discovery only exists on the oldest Dyson devices, and is an alternative to using cloud-based discovery to determine the local MQTT broker credentials.  A working example of sticker-based or "WiFi based" discovery may be found in libdyson-neon in utils.py (https://github.com/libdyson-wg/libdyson-neon/blob/main/libdyson/utils.py)  These methods will determine the serial number and MQTT password.  The username and hostname will be the serial number, and the password will be the MQTT password.  All other MQTT properties will need to be set by the user as defined in 

## Determining Device Capabilities

To avoid future product releases requiring a product update, we will be using the firmware capabilities as declared by the API to determine the entities to be created and how they should be expected to behave.  Capabilities are grouped by type and returned in the API at index [devices][unnamed_device_index][connected_configuration][firmware][device_apabilities].  These device capabilities will be used to group entities to attach to the device to allow for dynamic construction of a usable device with all features present.  For manual and sticker/"wifi-based" connections, these capability groups should be selectable by the end user in the Home Assistant UI during configuration or reconfiguration to grant manual users access to the same functionality.  The capabilities selected should create the device using the same method as a device discovered through the API and/or MQTT.

## Expected and Known Capabilities

"AdvanceOscillationDay1": Supports oscillation up to 350 degrees without wrap-around with high angle and low angle properties and on/off capabilities.
"Scheduling": Supports setting a timer to automatically power the device off when the timer expires.
"EnvironmentalData": Should indicate that the device supports temperature and humidity sensors.  The sensors should only populate if the temperature and humidity sensor keys are returned by the device.
"ExtendedAQ": Supports tracking PM2.5, PM10, CO2, NO2, and HCHO (Formaldehyde) metrics.  Will need entities for PM2.5, PM10, and a configuration option to enable or disable Continuous Monitoring.  Gas sensors should only be populated if their keys are seen in ENVIRONMENTAL-CURRENT-SENSOR-DATA responses
"ChangeWifi": Supports changing WiFi connection via bluetooth low energy or lec.  Support for this will need to be via bluetooth proxy.

All MQTT messages sent on `command` should include the following properties: `mode-reason`, with a constant value of "RAPP" indicating "remote app", `time` indicating the time the command is sent.
For all status messages, `time` is the time the device responded.

Status of all entities may be retrieved by sending an MQTT message on `command` topic similar to `{"msg":"REQUEST-CURRENT-STATE"}`.  This command is expected to be most useful when starting the integration to retrieve the state of all entities and for periodic state updates.  Multiple messages will be returned for this command on the `status/current` topic

"EnvironmentalData" and "ExtendedAQ" entities are expected to be read-only.  State may be requested through `command` topic:  `{"msg":"REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA"}` The device should respond on `status/current` topic similar to: `{"msg":"ENVIRONMENTAL-CURRENT-SENSOR-DATA","time":"2025-08-24T17:22:40.000Z","data":{"pm25":"0000","pm10":"0000","p25r":"0000","p10r":"0000","sltm":"OFF"}}` where `pm25` indicates the Particulate Matter 2.5 micron or PM2.5 quantity per cubic meter, `pm10` indicates the Particulate Matter 10 micron or PM10 quantity per cubic meter. `p25r` level should be displayed as P25R, `p10r` level should be displayed as P10R.  `sltm` is not used for air quality monitoring.  Continuous monitoring may be set through `command` topic with a message similar to `{"msg":"STATE-SET","data":{"rhtm":"OFF"}}` where `msg` is a constant of "STATE-SET", and `rhtm` is a boolean value of "ON" or "OFF".  State of continuous monitoring may be retrieved via message to `command` topic of `{"msg":"REQUEST-CURRENT-STATE"}` where `rhtm` indicates the state in boolean "ON" or "OFF".

"Scheduling" should be made available as Home Assistant services.  Scheduling may be performed by sending a message on the `command` topic similar to: `{"data":{"sltm":"0015"},"msg":"STATE-SET"}` where `msg` is a constant of "STATE-SET", `sltm` is the desired state of the sleep timer where OFF disables the sleep timer, and the sleep timer may be set through 4-digit integer in minutes.  Minimum should be `0015`, maximum should be `0540`.  State may be requested through `command` topic:  `{"msg":"REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA"}`.  The device should respond on `status/current` topic similar to: `{"msg":"ENVIRONMENTAL-CURRENT-SENSOR-DATA","time":"2025-08-24T17:22:40.000Z","data":{"pm25":"0000","pm10":"0000","p25r":"0000","p10r":"0000","sltm":"OFF"}}` where `sltm` is the current state of the sleep timer, either "OFF" if the sleep timer is disabled, or the 4-digit number of minutes remaining until the device will automatically power off.

"AdvanceOscillationDay1" entities should be considered read/write with appropriate command sent to the device when set.  These entities must support Home Assistant Scenes.  Setting the value on the device may be performed on `command` topic with a message similar to `{"msg":"STATE-SET","data":{"osau":"0257","osal":"0077","oson":"ON","ancp":"CUST"}}` where `msg` is a constant of "STATE-SET", `osau` sets the upper oscillation limit, `osal` sets the lower oscillation limit, `oson` sets the on/off value of oscillation, and `ancp` sets the center angle mode.  The only observed value for `ancp` is "CUST", but it is possible this field will receive a 4-digit integer as a preset list of angles.  Likely but untested values would be 45, 90, 135, 180, 225, 270, and 315.  State of oscillation may be retrieved through "REQUEST-CURRENT-STATE" as documented for status above, where `osau` indicates the current upper limit angle for oscillation, `osal` indicates the current lower limit angle for oscillation, `oson` indicates whether oscillation is ON or OFF, and `ancp` is the angle center point mode.  The properties of `ancp` in state are expected to match the observations and expectations documented for setting the value.

## Humidifier Capabilities

Humidifiers do not have their own capability declared by the Dyson API.  As a result, humidifiers should be determined by the product type, where a PH model (Purifier/Humidifer) should add our virtual capability to add humidifier controls and entities.
Hints for making Humidifier entities, but not the capability name, including their state key and possible values may be found by looking at functioning code in <https://github.com/cmgrayb/ha-dyson>.  Please update this section with data similar to the section in Expected and Known Capabilities once discovered and delete this message about hints.

## Heater Capabilities

Heaters do not have their own capability declared by the Dyson API.  As a result, heaters should be determined by the product type, where a HP model (Heater/Purifier) should add our virtual capability to add heater controls and entities.
Hints for making Heater entities, but not the capability name, including their state key and possible values may be found by looking at functioning code in <https://github.com/cmgrayb/ha-dyson>.  Please update this section with data similar to the section in Expected and Known Capabilities once discovered and delete this message about hints.

## Formaldehyde Capabilities

Hints for making Formaldehyde entities, but not the capability name, including their state key and possible values may be found by looking at functioning code in <https://github.com/cmgrayb/ha-dyson>.  Please update this section with data similar to the section in Expected and Known Capabilities once discovered and delete this message about hints.

## Unknown Capabilities

Additional capabilities that are known to exist but that we do not have examples for at this time include:

- Light functions

## Base Level Device Categories

### General

All devices will need to periodically poll on `command` topic `{"msg":"REQUEST-CURRENT-FAULTS"}` and generate an event in Home Assistant if any messages are returned on topic `status/fault`.  The description of the event should be "Device Fault Detected", with the content of the fault response in the value of the event.

### ec

"ec", or environment cleaning, devices are fans with filters.  All devices in this category are believed to support the following functionality:
- Fan on/off
- Fan speed (4-digit string 0001-0010 or "AUTO") - Should display without leading zeroes or "Automatic" in Home Assistant
- Fan Direction (normal/reverse)
- Filter Life
- Filter Type
- Night Mode - a configuration switch which sets the fan into a lower, quieter speed

ec devices should be created as `fan` `climate` devices in Home Assistant.

State of the above entities may be found in messages on the `status/current` topic in either `STATE-CHANGE` or `CURRENT-STATE` messages.  Requests to update status may be performed on the `command` topic with `{"msg":"REQUEST-CURRENT-STATE"}`  Messages of either type should immediately update the state in Home Assistant.  Night Mode may be determined by key `nmod` in boolean "ON" or "OFF".  Fan Speed state may be determined by key `fnsp`.  Auto mode may be determined by key `auto` with a boolean value of "ON" or "OFF".  For both getting and setting values, When `auto` is "ON", `fnsp` is expected to be "AUTO".  When `auto` is "OFF", `fnsp` is expected to be a 4-digit string.  Fan on/off status may be determined by `fnst`, which should be "OFF" if the fan is set to auto mode "ON" or if the device power is "OFF", and should have value "FAN" if auto mode is "OFF" and a numeric string value is set for `fnsp`.  Device on/off may be determined by key `fpwr` in boolean "ON" or "OFF".  Device on/off determines whether fan or auto may be used, and should be considered the "master" on/off switch.  Filter Life may be determined by keys `hflr` and `cflr`, where `hflr` is a HEPA-Carbon combination filter, and `cflr` is a Carbon Filter.  If no filter of that type is installed, the value will read `INV`.  Filter Type is read-only and may be determined by keys `hflt` and `cflt` respectively, where `hflt` will read "GCOM" for a Genuine Combi Filter.  Aftermarket combination filter value is not known, but assumed to not be "GCOM" or "NONE".  Genuine carbon filter value is not known but any filter installed is assumed to not be "NONE".  Both will read "NONE" if no filter of that type is installed.  A "Reset Filter Life" button should be created to call a Home Assistant Service or Action to reset the filter by sending `{"msg":"STATE-SET","data":{"hflr":"0100"}}` or `{"msg":"STATE-SET","data":{"cflr":"0100"}}` respectively.  The user should be able to choose the type of filter to reset in the service.  Fan Direction may be determined by key `fdir`, which may not be supported by all devices.  Devices which do not respond with `fdir` should store the user's last selected state and skip sending the command.  In all cases, setting the new desired value may be performed with `{"msg":"STATE-SET","data":{"key":"value"}}` where `key` is the key of the state to set, and `value` is its new value.

## light

"light" devices include Dyson's bluetooth/lec-only desk lamps and floor lamps.
Little is known about interaction with these devices at this time.  If an existing example can be found for how to communicate with them, we should support them as well.  Lights are the lowest priority for development due to lack of information and lack of device availability to test against.

## robot

"robot" devices are Dyson devices capable of piloting themselves.  These devices will need to return their current state and have control for whether or not they are currently operating.  A working example of most of these functions can be found in ha-dyson <https://github.com/cmgrayb/ha-dyson> and in libdyson-neon <https://github.com/cmgrayb/libdyson-neon>.  Information retrieved should be updated in this section.

## vacuum

"vacuum" devices are devices capable of using suction to clean an area.  These devices will need to return their current state and have control for whether or not they are currently operating.  If possible, setting which room they should clean should also be possible.  Only robotic vacuums (robot) devices are currently known to be available for this function.  A working example of most requested functions can be found in ha-dyson <https://github.com/cmgrayb/ha-dyson> and in libdyson-neon <https://github.com/cmgrayb/libdyson-neon>.  Information retrieved should be updated in this section.

## flrc

"flrc" devices are "floor cleaner" devices, which may or may not include vacuums.  Floor cleaner devices may also be hard floor devices, and thus may have an additional water tank in addition to waste storage to return in state.  Check against <https://github.com/cmgrayb/ha-dyson> for possible hints for these devices and in libdyson-neon <https://github.com/cmgrayb/libdyson-neon>.  Information retrieved should be updated in this section.

## wearable

"wearable" devices are not available to develop against at this time

## hc

"hc" or hair care devices are hair driers and curlers.  No known connectivity is available for them at this time.
