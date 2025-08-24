# Features

This document details the expected features of the integration when finished

## Setup

The setup of either a MyDyson API connection (libdyson-rest) or device connection (libdyson-mqtt) must be fully configurable, reconfigurable, and free to unload or reload from the UI at any time.

The configuration for MyDyson API should have configuration options for Polling Interval, where 0 indicates never, and Automatically Add Newly Discovered Devices as a boolean switch to allow the user to determine whether or not devices discovered on the account should be added without user interaction.

The integration must support multiple MyDyson accounts.  Failure to authenticate to an existing account should prompt the user to reconfigure that account to update the password.

MQTT device configurations must support require MQTT username, MQTT password, MQTT root topic, MQTT port, and have boolean inputs for all known capabilities to allow the user to configure what entities to attempt to support on the device.  MQTT device configurations should be usable for both automatically added devices and manually added devices.  Manually added devices should be treated as user-added devices which may or may not be on the MyDyson account.  The serial number should be used to determine the unique identifier for the device, and may be used to match the device to devices on the MyDyson account.

## Fetch Account Data

A Home Assistant Service or Action should be created to use an existing MyDyson API connection to fetch all known information about the account to be used for creating manual connections and for troubleshooting when desired.  The output of this service should be the json output demonstrated in libdyson-rest in the examples folder in file troubleshoot_account.py.

## Oscillation

Oscillation should be controlled through low angle, high angle, and center angle.  Angle selections of 45, 90, 180, 350, and Custom should be available to the user.  Center angle should be the median between low angle and high angle at all times and should adjust as other settings are adjusted.  Adjustment of center angle should respect the current angle selection and move the other sliders to compensate. Adjustment of the low or high angles should switch the angle selection to Custom.  Selection from any setting to Off or Off to any other selection should call the built-in Home Assistant Oscillation service to set it to On or Off respectively.  Concurrently, the Home Assistant Oscillation service should send the oson and osoff commands to MQTT to control the fan.  The entities must be available to get and set on the device for Home Assistant Scene support.  An example of this as described in another similar Home Assistant integration may be found at <https://github.com/cmgrayb/ha-dyson/tree/feature/state-based-oscillation>.  Should the description here conflict with calculation or function found in the GitHub branch, the working example should be considered more correct.

## Timer

Home Assistant should support setting, clearing and displaying a timer for any devices with a capability of "Scheduling".  Setting the timer should be performed through a Home Assistant Service to allow for Scripts and Actions are able to set the timer.

## Firmware Information

Firmware information is only available for devices discovered in the MyDyson API and cannot be supported for manually attached devices.  Firmware information may be found in the index [devices][unnamed_device_index][connected_configuration][firmware].  Firmware Version may be found at key `version` and is read-only, Auto-update Enabled is a read-write boolean true/false value and indicates whether or not the device will update its firmware without prompting the user.  Its key is `auto_update_enabled`.  New Version Available is a boolean read-only value with a key of `new_version_available`, and indicates to the user that a firmware update is available, regardless of whether `auto_update_enabled` is true.  The list returned in capabilities and how it is used is documented in `discovery.md`.  At this time, no information is known about requesting a manual firmware update using the API.