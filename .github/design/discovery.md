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

Some devices also broadcast on [model with or without variant]_[serial number]_360eye._mqtt._tcp, particularly robotic vacuums.  In the case that the device returns "robot", "vacuum" or "flrc" in the DeviceCategory (index [device][category] of the json response), this additional advertisement should be checked for.

## Sticker and "WiFi based" discovery

Sticker-based discovery only exists on the oldest Dyson devices, and is an alternative to using cloud-based discovery to determine the local MQTT broker credentials.  A working example of sticker-based or "WiFi based" discovery may be found in libdyson-neon in utils.py (https://github.com/libdyson-wg/libdyson-neon/blob/main/libdyson/utils.py)

## Determining Device Capabilities

To avoid future product releases requiring a product update, we will be using the firmware capabilities as declared by the API to determine the entities to be created and how they should be expected to behave.  Capabilities are grouped by type and returned in the API at index [devices][unnamed_device_index][connected_configuration][firmware][device_apabilities].  These device capabilities will be used to group entities to attach to the device to allow for dynamic construction of a usable device with all features present.  For manual and sticker/"wifi-based" connections, these capability groups should be selectable by the end user in the Home Assistant UI during configuration or reconfiguration to grant manual users access to the same functionality.  The capabilities selected should create the device using the same method as a device discovered through the API and/or MQTT.

## Expected and Known Capabilities

"AdvanceOscillationDay1": Supports oscillation up to 350 degrees without wrap-around with high angle and low angle properties and on/off capabilities.
"Scheduling": Supports setting a timer to automatically power the device off when the timer expires.
"EnvironmentalData": Supports tracking some form of environmental data.  Exactly which metrics are specific to this capability is unclear.  It is possible that this capability may be only be used as a meta-capability of all environment monitoring devices.  This should only be used as a last resort until purpose is determined.
"ExtendedAQ": Supports tracking PM2.5 and PM10 metrics.  Will need entities for PM2.5, PM10, and a configuration option to enable or disable Continuous Monitoring.
"ChangeWifi": Supports changing WiFi connection via API or MQTT.

## Unknown Capability Names

Additional capabilities that are known to exist but that we do not have examples for at this time include:

- Humidifier
- Heater
- Formaldehyde monitoring
- Light functions

## Base Level Device Categories

### ec

"ec", or environment cleaning, devices are fans with filters.  All devices in this category are believed to support the following functionality:
- Fan on/off
- Fan speed (4-digit string 0001-0010 or "AUTO") - Should display without leading zeroes or "Automatic" in Home Assistant
- Fan Direction (normal/reverse)
- Filter Life
- Night Mode - a configuration switch which sets the fan into a lower, quieter speed

## light

"light" devices include Dyson's bluetooth/lec-only desk lamps and floor lamps.
Little is known about interaction with these devices at this time.  If an existing example can be found for how to communicate with them, we should support them as well.  Lights are the lowest priority for development due to lack of information and availability to test against.

## robot

"robot" devices are Dyson devices capable of piloting themselves.  These devices will need to return their current state and have control for whether or not they are currently operating.  A working example of most of these functions can be found in ha-dyson <https://github.com/cmgrayb/ha-dyson>.

## vacuum

"vacuum" devices are devices capable of using suction to clean an area.  These devices will need to return their current state and have control for whether or not they are currently operating.  If possible, setting which room they should clean should also be possible.  Only robotic vacuums (robot) devices are currently known to be available for this function.  A working example of most requested functions can be found in ha-dyson <https://github.com/cmgrayb/ha-dyson>.

## flrc

"flrc" devices are "floor cleaner" devices, which may or may not include vacuums.  Floor cleaner devices may also be hard floor devices, and thus may have an additional water tank in addition to waste storage to return in state.

## wearable

"wearable" devices are not available to develop against at this time

## hc

"hc" or hair care devices are hair driers and curlers.  No known connectivity is available for them at this time.
