# HASS-Dyson Actions

## Get Cloud Devices Action

### Description

The Get Cloud Devices Action is added to Home Assistant when a cloud account is defined in the Dyson integration

The Action has two options:

1. Account E-mail: the email address associated with the desired account to query
    - If this is unconfigured or blank, the first account found will be queried
2. Sanitize Data: when run with this option selected, the action will return only the data that the developers will need to assist in adding a missing feature, with no identifiable or unique information included

### Purpose

Retrieve device data from the Dyson API

### Intended Use Cases

#### Home Assistant Native Manual Device Support

When Sanitize is set to off or false, the action will return all of the information required to create a manual device in the integration.

Note: When adding devices in this manner, some sensors and data, such as firmware, will not be available or show as unknown.

To create manual devices with a temporary cloud account connection:

1. Create a Dyson Cloud Account configuration.
2. When configuring Cloud Account Settings, deselect the options to `Poll for new devices` and `Automatically add discovered devices`
3. In Developer Tools > Actions, run Get Cloud Devices (hass_dyson.get_cloud_devices) with `Sanitize Data` unconfigured or off
4. Use the information returned to configure your devices manually
5. The cloud account may be removed at any time without affecting the manually added devices

#### Feature Request Device Information

When Sanitize is set to on or true, the action will return issue-safe information that the developers of the integration will need.
This data contains no identifiable or private information about your specific device, only the metadata required to identify the type of device that it is.

Including the output of the action in sanitize data mode will greatly improve the speed of resolution of your feature request or bug report.

## Refresh Account Data Action

### Description

The Refresh Account Data Action is added to Home Assistant when a cloud account is defined in the Dyson integration.

The Action has one optional parameter:

1. Device ID: the device identifier of a specific device to refresh
    - If this is unconfigured or blank, all devices will be refreshed

### Purpose

Manually trigger a refresh of device data from the Dyson cloud service for troubleshooting or immediate updates.

### Intended Use Cases

#### Troubleshooting Device State Issues

When device states appear out of sync or stale, this action can force an immediate refresh of device data from the cloud.

#### After Manual Device Changes

If you've made changes to a device through the Dyson app or physical controls, use this action to immediately sync those changes to Home Assistant.

## Set Sleep Timer Action

### Description

The Set Sleep Timer Action is available for individual Dyson devices that support sleep timer functionality.

The Action has two required parameters:

1. Device ID: the device identifier for the target device
2. Minutes: the sleep timer duration in minutes (15-540 minutes / 15 minutes to 9 hours)

### Purpose

Set a sleep timer on a Dyson device to automatically turn off after the specified duration.

### Intended Use Cases

#### Scheduled Device Shutdown

Set the device to automatically turn off after a specific duration, useful for bedtime routines or energy saving.

## Cancel Sleep Timer Action

### Description

The Cancel Sleep Timer Action is available for individual Dyson devices that support sleep timer functionality.

The Action has one required parameter:

1. Device ID: the device identifier for the target device

### Purpose

Cancel any active sleep timer on a Dyson device.

### Intended Use Cases

#### Manual Timer Cancellation

Remove an existing sleep timer if you want the device to continue running indefinitely.

## Set Oscillation Angles Action

### Description

The Set Oscillation Angles Action is available for individual Dyson devices that support oscillation angle control.

The Action has three required parameters:

1. Device ID: the device identifier for the target device
2. Lower Angle: the lower bound of oscillation in degrees (0-350°)
3. Upper Angle: the upper bound of oscillation in degrees (0-350°)

Note: Lower angle must be less than upper angle.

### Purpose

Configure the oscillation range for devices that support directional airflow control.

### Intended Use Cases

#### Targeted Airflow

Set specific oscillation angles to direct airflow to particular areas of a room or avoid obstacles.

#### Zone Control

Configure the device to oscillate only within a specific zone rather than the full range.

## Reset Filter Action

### Description

The Reset Filter Action is available for individual Dyson devices that have replaceable filters.

The Action has two required parameters:

1. Device ID: the device identifier for the target device
2. Filter Type: the type of filter to reset ("hepa", "carbon", or "both")

### Purpose

Reset the filter life counter after replacing filters, ensuring accurate filter life monitoring.

### Intended Use Cases

#### Post-Filter Replacement

After replacing a HEPA filter, carbon filter, or both, use this action to reset the filter life counters to 100%.

#### Maintenance Tracking

Ensure the device accurately tracks filter usage and provides correct replacement notifications.

## Schedule Operation Action (Experimental)

### Description

The Schedule Operation Action is an experimental feature available for individual Dyson devices.

The Action has three required parameters and one optional parameter:

1. Device ID: the device identifier for the target device
2. Operation: the operation to schedule ("turn_on", "turn_off", "set_speed", "toggle_auto_mode")
3. Schedule Time: the time to execute the operation in ISO format (e.g., "2025-01-01T12:00:00Z")
4. Parameters: optional JSON string with additional parameters for the operation

### Purpose

Schedule future operations on Dyson devices (experimental feature).

### Intended Use Cases

#### Future Automation

Schedule device operations to occur at specific times.

**Note**: This is an experimental feature and is not yet fully implemented. Currently, it only logs the scheduled operation for future development.