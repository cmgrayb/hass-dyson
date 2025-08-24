# Connecting

This file documents how the connection process to a Dyson device works to the best of knowledge.

## Connection Types

Different devices declare their connection methods as part of the API response, as returned by libdyson-rest.
Information on the different types of connections may be found in libdyson-rest in src/libdyson-rest/models/device.py in the docstring hints for ConnectionCategory
lecOnly devices and lec features of lecAndWifi devices should be handled via Home Assistant Bluetooth Proxy devices <https://esphome.io/components/bluetooth_proxy/>
lecOnly and lecAndWifi devices must follow the best practices and leverage the existing APIs as documented at <https://developers.home-assistant.io/docs/bluetooth>
lec connectivity should be handled by an imported external library.
lecAndWifi and wifiOnly devices may be connected to via MQTT and IoT.
If a suitable existing external library does not exist, the developer should be informed that one will need to be created.

## Device Configuration

A device with lecAndWifi or wifiOnly should have four options for connection type in the device configuration: "Local Only", "Local with Cloud Fallback", "Cloud with Local Fallback", and "Cloud", where "Local Only" disables IoT fallback, "Local with Cloud Fallback" attempts to make the connection using local MQTT information, then tries the IoT MQTT information, "Cloud with Local Fallback" enables a mode in which connection is tried using the IoT connection properties first, and then tries the local connection properties before failing, and "Cloud" always uses the IoT connection information and never local.  This configuration must be configurable while adding the device, default to "Local with Cloud Fallback", and be reconfigurable at any time.  The descriptions should indicate the benefits of each, where "Local Only" maximizes privacy and ensures function with no internet, "Local with Cloud Fallback" attempts to maximize privacy, but allows for cloud fallback in case of local connectivity problems.  "Cloud with Local Fallback" uses the more reliable Dyson-hosted MQTT proxy to connect to the device by default, but falls back to local in the case that internet connectivity is lost.  "Cloud Only" always uses the Dyson-hosted MQTT proxy in the case that the local network is unable to support mDNS/Zeroconf.

lec devices should have an option to pin the connection to a specific bluetooth proxy to ensure that the connection is performed at the nearest tranceiver to the device, if the bluetooth proxy framework supports such a function.  Automatic detection of best proxy to use should be the default configuration.

## MQTT Connection

In the case of devices labeled lecAndWifi or wifiOnly, the devices should be connected to using libdyson-mqtt.
The connection information needs to be queried from the API or supplied by the end user in the case of a manually created or sticker/wifi info connection, including the username, password, serial number, and MQTT root topic.
The connection should remain up at all times when the integration is running, stopping only on shutdown, restart, or reconfiguration.

## "IoT" connection

Any devices supporting lecAndWifi or wifiOnly should also support the Dyson-hosted MQTT broker proxy connections as well.  These connections should only be used if the user explicitly configures the device for IoT or IoT Fallback.  All inputs are expected to match the Local MQTT Connection excepting hostname, username, and password, which should be taken from the IoT section of the API response.  Whether or not this connection should be used should be determined by the setting for "Local Only", "Local with Cloud Fallback", "Cloud with Local Fallback" and "Cloud" detailed in the Device section.

## MQTT Topics

All devices appear to follow a similar pattern with regard to MQTT topics.  However, there is a high likelihood that these topics may change in the future, so their definition should be easy to update later.
The topics may be calculated as follows: [MQTT Root Topic]/[Serial Number]/[Topic], where the minimum list of topics should be:

- command
- status/current
- status/faults

## MQTT Remote Broker Type

Returned in the MQTT connection information from the API under index [devices][unnamed_device_index][connected_configuration][mqtt][remote_broker_type] is the connection type to use to connect to MQTT.  Currently, the only known type is "wss" indicating a websocket connection.  This information will likely become relevant in the future when interacting with libdyson-mqtt and should be stored for future use in the Home Assistant configuration for the device.  If an option for connection type exists in libdyson-mqtt, the option should be set to use the value returned by the API.

## Status Refresh

Dyson devices do not inherently broadcast their state changes.  To get a status update, the integration should periodically poll for status using MQTT message `{"msg": "REQUEST-CURRENT-STATE", "time": datetime.now().isoformat()}` on the command topic and then listen to the status topic for the latest device state.  State should be updated in Home Assistant immediately upon receipt.  Interval should be user-configurable but default to around 10 seconds.  More information on this may be found in discovery.md

## Known Device Limitations

The local broker on Dyson devices is known to occasionally not be ready when first attempting to connect.  As such, several attempts should be made using a progressively longer delay before moving to the fallback connection method, if one is set, or declaring a connection failure if not.