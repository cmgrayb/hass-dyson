# TO DO

## Open Items

- [ ] **Refactor fault sensor entity names to use HA translation files** — `DysonFaultSensor` in `binary_sensor.py` sets `_attr_name` via a hardcoded Python dict (`_get_fault_friendly_name()`), bypassing HA's translation system. Each fault code (e.g. `tnke`, `tnkp`, `aqs`) needs a unique `translation_key` wired to `translations/en.json` (and `de.json`, `fr.json`) for proper i18n support. The `FAULT_TRANSLATIONS` attribute messages in `const.py` are a separate concern (used for `extra_state_attributes`) and should also be evaluated for translation.

- [ ] **Refactor: Correct Startup Speed Improvement** (`refactor/startup_speed`)

**Context:**
Branch `refactor/startup_speed` aimed to reduce HA startup time by deferring the coordinator's
initial data fetch to a background task.  The approach introduced a regression: every entity
whose creation is gated on `coordinator.data` at platform-setup time is silently skipped because
`coordinator.data` is `None` when `async_setup_entry` runs for each platform.

The branch already contains the genuine performance win — `_wait_for_initial_mqtt_data` replaces
two fixed `asyncio.sleep(0.5)` calls in `_async_update_data` with responsive polling (typical
improvement from ~500–1000 ms to ~140–250 ms per device).  The regression must be corrected
before the branch is merged.

### Affected entities (silently skipped when `coordinator.data` is `None`)

**`sensor.py` — gated on `coordinator.data["environmental-data"]`**

| Entity | Key | Capability gate |
|---|---|---|
| `DysonParticulatesSensor` | `pact` | `EnvironmentalData` or `ExtendedAQ` |
| `DysonPM25Sensor` | `p25r` / `pm25` | `EnvironmentalData` or `ExtendedAQ` |
| `DysonPM10Sensor` | `p10r` / `pm10` | `EnvironmentalData` or `ExtendedAQ` |
| `DysonVOCLinkSensor` | `vact` (not `va10`) | `EnvironmentalData` or `ExtendedAQ` |
| `DysonCO2Sensor` | `co2r` | `ExtendedAQ` |
| `DysonNO2Sensor` | `noxl` | `ExtendedAQ` |
| `DysonVOCSensor` | `va10` | `ExtendedAQ` |
| `DysonFormaldehydeSensor` | `hchr` / `hcho` | `ExtendedAQ` |

**`sensor.py` — gated on `coordinator.data["product-state"]`**

| Entity | Key | Capability gate |
|---|---|---|
| `DysonCarbonFilterLifeSensor` / `DysonCarbonFilterTypeSensor` | `cflt` | `EnvironmentalData` or `ExtendedAQ` |

**`select.py` — gated on `coordinator.data["product-state"]`**

| Entity | Key | Gating |
|---|---|---|
| `DysonTiltOscillationModeSelect` | `oton` | `ec` category device |

### What to keep vs. revert

| Change | Action | Reason |
|---|---|---|
| `_wait_for_initial_mqtt_data()` method | **Keep** | The actual performance win — smarter waiting in `_async_update_data` |
| `_wait_for_initial_mqtt_data` call sites in `_async_update_data` | **Keep** | Replaces fixed 500 ms sleeps with responsive polling |
| `_start_cloud_coordinator_refresh` background task | **Keep** | Cloud account coordinator does not gate entity creation — safe to defer |
| Background firmware check | **Keep** | Firmware check was never critical to setup |
| `await coordinator._async_setup_device()` replacing `async_config_entry_first_refresh()` | **Revert** | Breaks `coordinator.data` population that all platform setups depend on |
| `_run_initial_device_refresh` background task and function | **Remove** | Redundant once the synchronous first refresh is restored |

### Implementation steps

**Step 1 — `__init__.py`: Restore `async_config_entry_first_refresh`**

In `_setup_individual_device_entry`, replace the direct call to `_async_setup_device()` with the
full `async_config_entry_first_refresh()` and remove the `_run_initial_device_refresh` background
task immediately below it.

```python
# Before (this branch — broken)
await coordinator._async_setup_device()
...
hass.async_create_background_task(
    _run_initial_device_refresh(coordinator, entry),
    f"dyson_initial_refresh_{coordinator.serial_number}",
)

# After (correct)
await coordinator.async_config_entry_first_refresh()
```

The `UnsupportedDeviceError` catch block is unchanged — `_async_setup_device()` is still called
inside `async_config_entry_first_refresh()` and raises the same exception.

**Step 2 — `__init__.py`: Remove `_run_initial_device_refresh`**

Delete the `_run_initial_device_refresh` function entirely.

**Step 3 — `coordinator.py`: No changes needed**

`_wait_for_initial_mqtt_data` and its two call sites in `_async_update_data` are kept as-is.
Now that `async_config_entry_first_refresh()` calls `_async_update_data()` synchronously, the
responsive polling executes during startup and delivers the speed benefit.

**Step 4 — Tests**

- Revert `test_async_setup_entry_basic`, `test_async_setup_entry_unsupported_device_schedules_removal`,
  and `test_async_setup_entry_platform_error_handling` from mocking `_async_setup_device` back to
  mocking `async_config_entry_first_refresh`.
- Remove the four `TestInitBackgroundTasks` tests for `_run_initial_device_refresh`.
- Keep the `TestWaitForInitialMqttData` tests in `test_coordinator.py` — they cover the coordinator
  improvement that is being retained.

**Step 5 — Verify**

```bash
python -m pytest tests/test_init.py tests/test_coordinator.py -v
python -m pytest tests/test_sensor_setup_coverage.py -v
python -m pytest -v
```

### Net result

| Metric | `main` (before branch) | This branch (broken) | After fix |
|---|---|---|---|
| Blocking time per device | ~500–1000 ms fixed | ~0 ms (broken) | ~140–250 ms typical |
| `coordinator.data` ready before platform setup | ✅ | ❌ | ✅ |
| All data-gated entities detected correctly | ✅ | ❌ | ✅ |
| Cloud coordinator non-blocking | ❌ | ✅ | ✅ |
| Firmware check non-blocking | ❌ | ✅ | ✅ |

