# Humidifier Support

## Detection

Populate humidifier sensors and controls based on presence of "hume" key for cloud discovery
Populate humidifier sensors and controls based on capability "Humidifier" for manual discovery

## Climate Controls

When a humidifier is detected, a climate entity must be created.  All climate controls should
be attached to the native properties and methods of the climate entity.

The existing climate entity class should be reused, changing the logic to populate on _either_
heating or humidifier capability detection.

### Mode Controls

If possible, this should be a single mode select list in the climate entity with options for
Off, On, and Auto.  When set to Off, both hume and haut should send "OFF".  In all cases,
changing the state in Home Assistant should send the appropriate key/value pair using
send_command and update the value on status updates from the device.

#### Humidification Enabled

Mode option On
Key: hume (humidity enabled)
Values:
  On: HUMD
  Off: OFF

#### Automatic Humidification

Mode option Auto
Key: haut (humidity auto)
Values:
  On: ON
  Off: OFF

### Humidistat

Little is known about the "rect" key, and it should be left out until otherwise determined
to be useful.  The climate humidity target should set the humt value with send_command and
should update the current value when status updates from the device.

Key: humt (humidity target)
Known working values:
  Min: 0030
  Max: 0050

Key: rect (automatic humidity target) (may be legacy)
Known working values:
  None - read only?

## Configuration Controls

The only known configuration option for the humidifier models is Water Hardness.
This select control should be appended to any devices reporting a hume key in status.
This control should set the key specified with the values below and update when the
device sends status updates.

### Water Hardness

Key: wath (water hardness)
Known working values:
  Soft: 2025
  Medium: 1350
  Hard: 0675

## Additional Sensors

All sensors on this list are read-only to the best of our knowledge
These sensors should update whenever the device sends back a status update

### Next Cleaning Cycle

Key: cltr (clean time remaining)
Value: 4-digit response in hours

### Cleaning Cycle Time Remaining

Key: cdrr (clean/descale removal remaining?)
Value: 4-digit response in minutes

## Fault Sensors - Warnings (Diagnostics in Home Assistant)

All sensors on this list are read-only to the best of our knowledge
All sensors on this list require periodic polling to REQUEST-CURRENT-FAULTS to be seen
All sensors on this list return on message CURRENT-FAULTS in the MQTT topic ending in
status/faults in the product-warnings section
All sensors on this list should update whenever receiving a CURRENT-FAULTS message
All sensors on this list return FAIL if there is a problem, and OK under normal operation

Example given by issue opener of MQTT CURRENT-FAULTS response from a humidifier model:

```json
{
  "msg": "CURRENT-FAULTS",
  "time": "[datetime]",
  "product-errors": {
    "amf1": "OK",
    "amf2": "OK",
    "amf3": "OK",
    "amf4": "OK",
    "amf5": "OK",
    "amf6": "OK",
    "amf7": "OK",
    "amf8": "OK",
    "amf9": "OK",
    "com4": "OK",
    "com1": "OK",
    "iuh0": "OK",
    "iup0": "OK",
    "iuw0": "OK",
    "iuh1": "OK",
    "iuu1": "OK",
    "iuc1": "OK",
    "iuw1": "OK",
    "iua1": "OK",
    "iuh2": "OK",
    "iuu2": "OK",
    "iuc2": "OK",
    "iuw2": "OK",
    "iua2": "OK",
    "iuh4": "OK",
    "iuu4": "OK",
    "iuc4": "OK",
    "iuw4": "OK",
    "iua4": "OK",
    "ui01": "OK",
    "ui02": "OK",
    "ui03": "OK",
    "uid1": "OK",
    "uid2": "OK",
    "fs01": "OK",
    "fs02": "OK",
    "fs03": "OK",
    "fs04": "OK",
    "fs05": "OK",
    "fs06": "OK",
    "fs07": "OK",
    "fs08": "OK",
    "fs09": "OK",
    "fs0a": "OK",
    "fs0b": "OK",
    "fs0c": "OK",
    "psu1": "OK",
    "psu2": "OK",
    "sen1": "OK",
    "sen2": "OK",
    "sen3": "OK",
    "sen4": "OK",
    "sen7": "OK",
    "com5": "OK",
    "com2": "OK",
    "com9": "OK",
    "coma": "OK",
    "bosl": "OK",
    "bosr": "OK",
    "etws": "OK",
    "wpmp": "OK",
    "prot": "OK",
    "uled": "OK"
  },
  "product-warnings": {
    "fltr": "OK",
    "tnke": "FAIL",
    "tnkp": "OK",
    "cldu": "OK",
    "etwd": "OK"
  },
  "module-errors": {
    "szme": "OK",
    "szmw": "OK",
    "szps": "OK",
    "szpe": "OK",
    "szpw": "OK",
    "szed": "OK",
    "lspd": "OK",
    "szpi": "OK",
    "szpp": "OK",
    "szhv": "OK",
    "szbv": "OK",
    "szav": "OK"
  },
  "module-warnings": {
    "srnk": "OK",
    "stac": "OK",
    "strs": "OK",
    "srmi": "OK",
    "srmu": "OK",
    "nwcs": "OK",
    "nwts": "OK",
    "nwps": "OK",
    "nwss": "OK"
  }
}
```

### Tank Empty

Key: tnke (tank empty)

### Filter

Key: fltr (filter)

### TNKP

Key: tnkp (purpose unknown)

### CLDU

Key: cldu (purpose unknown)

### ETWD

Key: etwd (purpose unknown)
