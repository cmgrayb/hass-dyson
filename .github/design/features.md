# Features

This document details the expected features of the integration when finished

## Setup

The setup of MyDyson API-based connections (libdyson-rest) for discovery must be fully configurable, reconfigurable, and free to unload or reload within Home Assistant at any time.  The integration must support multiple MyDyson accounts.  Failure to authenticate to an existing account should prompt the user to reconfigure that account to update the password.

The setup of manually created or sticker/"wifi based" devices must also support multiple devices, and will need to prompt the user for MQTT username, password, root topic, and list capabilities to select for the device.  Reconfiguration of existing devices must be available to update the device's connection properties.

## Oscillation

Oscillation should be controlled through low angle, high angle, and center angle.  Angle selections of 45, 90, 180, 350, and Custom should be available to the user.  Center angle should be the median between low angle and high angle at all times and should adjust as other settings are adjusted.  Adjustment of center angle should respect the current angle selection and move the other sliders to compensate. Adjustment of the low or high angles should switch the angle selection to Custom.  Selection from any setting to Off or Off to any other selection should call the built-in Home Assistant Oscillation service to set it to On or Off respectively.  Concurrently, the Home Assistant Oscillation service should send the oson and osoff commands to MQTT to control the fan.  An example of this in action in another similar Home Assistant integration may be found at <https://github.com/cmgrayb/ha-dyson/tree/feature/state-based-oscillation>

## Timer

Home Assistant should support setting, clearing and displaying a timer for any devices with a capability of "Scheduling"
