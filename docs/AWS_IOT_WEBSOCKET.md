# AWS IoT WebSocket MQTT Implementation

## Overview

This document describes the AWS IoT WebSocket MQTT implementation for Dyson cloud devices, which enables secure communication with Dyson devices through Amazon Web Services IoT infrastructure.

## Background

Dyson air purifiers and fans can operate in multiple connection modes:
- **Local MQTT**: Direct connection to device on local network (port 1883)
- **Cloud MQTT**: Connection through AWS IoT WebSocket (port 443)

The cloud connection is required when:
- Device is not on the same local network
- Local network access is restricted
- Remote monitoring is needed
- Device is configured for cloud-only operation

## Technical Implementation

### Connection Detection

The integration automatically detects when AWS IoT WebSocket is required by checking the `remote_broker_type` field in the device configuration:

```json
{
  "connected_configuration": {
    "mqtt": {
      "remote_broker_type": "wss"
    }
  }
}
```

When `remote_broker_type` is `"wss"`, the system uses the AWS IoT WebSocket implementation.

### AWS IoT Credentials Structure

AWS IoT connections require the following credential structure:

```json
{
  "endpoint": "a1u2wvl3e2lrc4-ats.iot.eu-west-1.amazonaws.com",
  "client_id": "b400e424-135b-4105-aa46-bb69b71944ea",
  "token_value": "b400e424-135b-4105-aa46-bb69b71944ea",
  "token_signature": "qHwSyHLLtB1+0cAxoq1mC...",
  "remote_broker_type": "wss"
}
```

### Connection Process

1. **Credential Parsing**: Extract AWS IoT credentials from JSON structure
2. **WebSocket URL Construction**: Create WebSocket path with authorization parameters
3. **MQTT Client Setup**: Configure paho-mqtt with WebSocket transport
4. **TLS Configuration**: Set up SSL context with proper verification
5. **Connection Establishment**: Connect to AWS IoT endpoint on port 443
6. **Authentication**: Use Dyson's AWS IoT Custom Authorizer

### Code Implementation

#### Credential Extraction (coordinator.py)

```python
# Extract AWS IoT credentials from device API response
iot_credentials = device_data.get("iot_credentials", {})
mqtt_config = device_data.get("connected_configuration", {}).get("mqtt", {})
remote_broker_type = mqtt_config.get("remote_broker_type", "mqtt")

if iot_credentials.get("endpoint") and iot_credentials.get("credentials"):
    cloud_credential = json.dumps({
        "endpoint": iot_credentials["endpoint"],
        "client_id": iot_credentials["credentials"]["client_id"],
        "token_value": iot_credentials["credentials"]["token_value"],
        "token_signature": iot_credentials["credentials"]["token_signature"],
        "remote_broker_type": remote_broker_type
    })
```

#### WebSocket Connection (device.py)

```python
async def _attempt_aws_iot_websocket_connection(self, host: str, credential: str) -> bool:
    """Attempt AWS IoT WebSocket MQTT connection."""
    
    # Parse AWS IoT credentials
    cred_data = json.loads(credential)
    endpoint = cred_data["endpoint"]
    client_id = cred_data["client_id"]
    token_value = cred_data["token_value"]
    token_signature = cred_data["token_signature"]
    
    # Create authentication parameters
    auth_params = {
        "token": token_value,
        "signature": token_signature
    }
    
    # Create MQTT client with WebSocket transport
    mqtt_client = mqtt.Client(
        client_id=f"dyson-ha-cloud-{self.serial_number}-{uuid.uuid4().hex[:8]}",
        transport="websockets"
    )
    
    # Set WebSocket options with custom authorization
    mqtt_client.ws_set_options(
        path=f"/mqtt?{urlencode(auth_params)}",
        headers=None
    )
    
    # Set up TLS context for WebSocket Secure (WSS)
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    mqtt_client.tls_set_context(context)
    
    # Connect to AWS IoT endpoint on port 443
    result = await self.hass.async_add_executor_job(mqtt_client.connect, endpoint, 443, 60)
    
    return result == mqtt.CONNACK_ACCEPTED
```

## Security Considerations

### TLS/SSL Configuration

- Uses TLS 1.2+ for all WebSocket connections
- Validates server certificates with proper hostname verification
- Requires valid AWS IoT endpoint certificates

### Authentication

- Uses Dyson's AWS IoT Custom Authorizer
- Token-based authentication with cryptographic signatures
- No username/password authentication required
- Tokens are passed as URL parameters in WebSocket handshake

### Network Security

- All traffic encrypted with TLS
- Connects to verified AWS IoT endpoints only
- Uses secure WebSocket (WSS) protocol on port 443
- Supports AWS IoT rate limiting and throttling

## Error Handling

### Connection Failures

- **Invalid Credentials**: Detailed logging of credential validation errors
- **Network Issues**: Timeout handling and retry logic
- **SSL/TLS Errors**: Certificate validation error reporting
- **AWS IoT Errors**: Proper MQTT error code handling

### Fallback Strategy

The integration supports automatic fallback:
1. **Primary**: AWS IoT WebSocket (cloud)
2. **Fallback**: Local MQTT (if available)

### Logging

Debug logging includes:
- Connection attempt details
- Credential validation (without sensitive data)
- WebSocket handshake information
- MQTT connection status
- Error details for troubleshooting

## Dependencies

### Required Libraries

- `paho-mqtt>=1.6.0`: MQTT client with WebSocket support
- `websockets>=10.0`: WebSocket protocol implementation
- `cryptography>=3.4.0`: SSL/TLS cryptographic functions

### Home Assistant Integration

- Uses `hass.async_add_executor_job()` for thread safety
- Integrates with Home Assistant's async event loop
- Supports Home Assistant's connection retry mechanisms

## Troubleshooting

### Common Issues

1. **Connection Timeout**
   - Check internet connectivity
   - Verify AWS IoT endpoint accessibility
   - Check firewall settings for port 443

2. **Authentication Failures**
   - Validate AWS IoT credentials format
   - Check token expiration
   - Verify custom authorizer configuration

3. **SSL/TLS Errors**
   - Ensure system clock is correct
   - Update CA certificate bundles
   - Check TLS version compatibility

### Debug Steps

1. Enable debug logging for `custom_components.hass_dyson.device`
2. Check Home Assistant logs for connection attempts
3. Verify device API response contains valid `iot_credentials`
4. Test local connectivity to rule out device issues

## Performance Considerations

### Connection Management

- Single WebSocket connection per device
- Automatic reconnection on connection loss
- Efficient MQTT message handling
- Minimal memory footprint

### Scalability

- Supports multiple devices simultaneously
- Each device uses independent AWS IoT connection
- Proper resource cleanup on disconnection
- Thread-safe implementation

## Future Enhancements

### Planned Features

- Connection quality metrics
- Advanced retry strategies
- Regional endpoint optimization
- Enhanced error reporting

### AWS IoT Integration

- Support for AWS IoT Device Shadows
- Integration with AWS IoT Analytics
- Custom MQTT topic filtering
- Advanced AWS IoT feature utilization

## Testing

### Unit Tests

AWS IoT WebSocket functionality is tested with:
- Mock MQTT clients
- Simulated credential parsing
- SSL context validation
- Error condition testing

### Integration Tests

Real-world testing includes:
- Live AWS IoT connections
- Multiple device types
- Network failure scenarios
- Long-running stability tests

## References

- [AWS IoT Core WebSocket Guide](https://docs.aws.amazon.com/iot/latest/developerguide/mqtt-ws.html)
- [Paho MQTT WebSocket Documentation](https://github.com/eclipse/paho.mqtt.python)
- [Home Assistant Integration Guidelines](https://developers.home-assistant.io/docs/integration_quality_scale)
