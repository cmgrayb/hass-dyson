# General Notes

This document contains high level notes about the integration which may be necessary background information to build or update the integration.

## Project Overview

This is a Python 3 Home Assistant integration for interacting with the Dyson REST and WebSocket API, as well as Dyson products over MQTT. The integration is designed to be consumed as public code and must maintain high code quality standards.  It is expected to first be published in HACS during User Acceptance Testing, then added to the Home Assistant core integrations.

## Overlapping Terminology

"WiFi-based": Indicates that the device likely will be listed as wifiOnly in the API.  The device is advertising its connection information through an available onboard WiFi access point for configuration.
"Sticker": Indicates that there is a sticker on the device with the connection information.
"IoT Connection": The connection to the Dyson-managed, cloud-based, MQTT broker proxy for the device.

## Appearance

All entities should use an appropriate icon from the material design icon (mdi:) set.

The integration should use the logo found in the root of the repository titled dyson-logo.svg.  If the location would be more appropriate in a subfolder for cleanliness or security reasons, it should be moved.

## Target Version

This integration must be compatible with Home Assistant 2025.12 and above.
