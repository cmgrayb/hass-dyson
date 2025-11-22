# TO DO

## Humidifier Support

### Detection

Populate humidifier sensors and controls based on presence of "hume" key for cloud discovery
Populate humidifier sensors and controls based on capability "Humidifier" for manual discovery

## Climate Controls

### Mode Controls

#### Humidification Enabled

Key: hume (humidity enabled)
Values:
  On: HUMD
  Off: OFF

#### Automatic Humidification

Key: haut (humidity auto)
Values:
  On: ON
  Off: OFF

### Humidistat

Key: humt (humidity target)
Known working values:
  Min: 0030
  Max: 0050

Key: rect (automatic humidity target) (may be legacy)
Known working values:
  None - read only?

## Configuration Controls

### Water Hardness

Key: wath (water hardness)
Known working values:
  Soft: 2025
  Medium: 1350
  Hard: 0675

## Additional Sensors

### Next Cleaning Cycle

Key: cltr (clean time remaining)
Value: 4-digit response in hours

### Cleaning Cycle Time Remaining

Key: cdrr (clean/descale removal remaining?)
Value: 4-digit response in minutes

## Fault Sensors - Warnings

All sensors on this list require periodic polling to REQUEST-CURRENT-FAULTS to be seen
All sensors on this list return on message CURRENT-FAULTS in the MQTT topic ending in status/faults in the product-warnings section
All sensors on this list return FAIL if there is a problem, and OK under normal operation

Example given by issue opener of MQTT response:

```
{
  "msg": "CURRENT-FAULTS",
  "time": "[datetime]",
  "product-errors": {
    "amf1": "OK",
    ...
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
    ...
    "szav": "OK"
  },
  "module-warnings": {
    "srnk": "OK",
    ...
    "nwss": "OK"
  }
}
```

### Tank Empty

Key: tnke (tank empty)

### Tank P---?

Key: tnkp (purpose unknown)

### Filter

Key: fltr (filter)

### CLDU

Key: cldu (purpose unknown)

### ETWD

Key: etwd (purpose unknown)
