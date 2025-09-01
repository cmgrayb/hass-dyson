# Dependencies

This file documents the dependencies used by the integration and how they are used

## libdyson-rest

This integration should leverage libdyson-rest, found on GitHub at https://github.com/cmgrayb/libdyson-rest

- Library libdyson-rest is owned by the same product group and may be updated as needed with detailed instructions that can be passed to another copilot instance without confusion or misinterpretation
- libdyson-rest is to be used for any connections to the Dyson cloud API for authentication and discovery of devices

## paho-mqtt

This integration uses paho-mqtt directly for MQTT communication instead of an intermediate library. This approach provides:

- Direct control over MQTT connection handling and message processing
- Better integration with Home Assistant's async architecture
- Reduced dependency chain and potential compatibility issues
- Full access to all MQTT features and configuration options

The integration handles MQTT connections for both:
- Direct connections to device onboard WiFi/MQTT brokers
- "IoT" connections through Dyson's cloud-hosted MQTT proxy
