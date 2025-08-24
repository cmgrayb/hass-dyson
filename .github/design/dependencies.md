# Dependencies

This file documents the dependencies used by the integration and how they are used

## libdyson-rest

This integration should leverage libdyson-rest, found on GitHub at https://github.com/cmgrayb/libdyson-rest

- Library libdyson-rest is owned by the same product group and may be updated as needed with detailed instructions that can be passed to another copilot instance without confusion or misinterpretation
- libdyson-rest is to be used for any connections to the Dyson cloud API for authentication and discovery of devices

## libdyson-mqtt

This integration should leverage libdyson-mqtt, found on GitHub at https://github.com/cmgrayb/libdyson-mqtt

- Library libdyson-mqtt is owned by the same product group and may be updated as needed with detailed instructions that can be passed to another copilot instance without confusion or misinterpretation
- libdyson-mqtt is to be used for any connections leveraging the mqtt protocol, including direct connections via the device's onboard WiFi, or "IoT" connections leveraging Dyson's cloud-hosted MQTT proxy
