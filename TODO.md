# TO DO

## Open Items

- [ ] **Use `UpdateFailedUnreachable` for device connectivity failures** — In a future release, review the main device coordinator's update failures and use this exception for genuine device or service reachability failures, such as a disconnected device. Keep authentication, configuration, and other non-reachability failures distinct. Check compatibility with the supported Home Assistant versions and provide the translation needed for the unavailable log message.
- [ ] **Refactor fault sensor entity names to use HA translation files** — `DysonFaultSensor` in `binary_sensor.py` sets `_attr_name` via a hardcoded Python dict (`_get_fault_friendly_name()`), bypassing HA's translation system. Each fault code (e.g. `tnke`, `tnkp`, `aqs`) needs a unique `translation_key` wired to `translations/en.json` (and `de.json`, `fr.json`) for proper i18n support. The `FAULT_TRANSLATIONS` attribute messages in `const.py` are a separate concern (used for `extra_state_attributes`) and should also be evaluated for translation.

---
