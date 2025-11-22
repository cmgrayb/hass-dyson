"""Base entity class for Dyson integration.

This module provides the DysonEntity base class that all Dyson Home Assistant
entities inherit from. It implements common functionality for device integration,
state management, and coordinator interaction patterns.

Key Features:
    - Automatic device information linking for Home Assistant device registry
    - Availability management based on coordinator and device connection status
    - Thread-safe coordinator update handling
    - Consistent entity naming with _attr_has_entity_name = True
    - Type-safe coordinator access with proper type annotations

Inheritance Chain:
    DysonEntity → CoordinatorEntity → Entity (Home Assistant base)

Usage Pattern:
    All Dyson platform entities (fan, sensor, climate, etc.) should inherit
    from DysonEntity to ensure consistent behavior and device integration.

Example:
    Creating a custom Dyson entity:

    >>> class DysonCustomEntity(DysonEntity, SensorEntity):
    >>>     def __init__(self, coordinator: DysonDataUpdateCoordinator):
    >>>         super().__init__(coordinator)
    >>>         self._attr_unique_id = f"{coordinator.serial_number}_custom"
    >>>         # Entity automatically gets device_info and availability
"""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DysonDataUpdateCoordinator


class DysonEntity(CoordinatorEntity):
    """Base class for all Dyson entities with integrated device management.

    This class provides common functionality for all Dyson entities including
    device information management, availability determination, and coordinator
    update handling. It ensures consistent behavior across all entity types.

    Attributes:
        coordinator: DysonDataUpdateCoordinator instance providing device access
        _attr_has_entity_name: Always True for modern Home Assistant naming

    Properties:
        device_info: Device information dict for Home Assistant device registry
        available: Entity availability based on coordinator and connection status

    Key Features:
        - Automatic device registry linking via device_info property
        - Smart availability management considering coordinator and device state
        - Thread-safe update handling for coordinator changes
        - Type-safe coordinator access with proper annotations

    Availability Logic:
        Entity is available when ALL conditions are met:
        1. Coordinator last_update_success is True
        2. Coordinator has a device instance (not None)
        3. Device reports is_connected as True

    Thread Safety:
        Update handling is thread-safe using hass.loop.call_soon_threadsafe
        to ensure all updates occur in the main Home Assistant event loop.

    Example:
        Subclassing for custom entities:

        >>> class DysonTemperatureSensor(DysonEntity, SensorEntity):
        >>>     def __init__(self, coordinator):
        >>>         super().__init__(coordinator)
        >>>         self._attr_unique_id = f"{coordinator.serial_number}_temperature"
        >>>         self._attr_device_class = SensorDeviceClass.TEMPERATURE
        >>>
        >>>     @property
        >>>     def native_value(self):
        >>>         return self.coordinator.device.temperature if self.available else None

    Note:
        All Dyson entities should inherit from this class rather than directly
        from CoordinatorEntity to ensure consistent device integration behavior.

    Raises:
        TypeError: If coordinator is not a DysonDataUpdateCoordinator instance
    """

    coordinator: DysonDataUpdateCoordinator
    _attr_has_entity_name = True

    def __init__(self, coordinator: DysonDataUpdateCoordinator) -> None:
        """Initialize the Dyson entity."""
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Return device information for Home Assistant device registry.

        Returns:
            Dict containing device information if device is available:
            - identifiers: Unique device identifiers for registry linking
            - name: Human-readable device name
            - manufacturer: Always "Dyson"
            - model: Device model/type identifier
            - sw_version: Current firmware version
            - hw_version: Hardware version if available

            None if coordinator has no device instance.

        Note:
            This property enables Home Assistant to group all entities
            from the same physical device together in the device registry.
            The device_info is sourced from the DysonDevice instance.

        Example:
            Typical device_info structure:

            >>> {
            >>>     "identifiers": {("hass_dyson", "VS6-EU-HJA1234A")},
            >>>     "name": "Living Room Dyson",
            >>>     "manufacturer": "Dyson",
            >>>     "model": "Pure Cool Link Tower (438)",
            >>>     "sw_version": "21.03.08"
            >>> }
        """
        if self.coordinator.device:
            return self.coordinator.device.device_info
        return None

    @property
    def available(self) -> bool:
        """Return entity availability based on coordinator and device status.

        Returns:
            True if entity should be considered available for operations,
            False if entity should be marked as unavailable in Home Assistant.

        Availability Criteria:
            Entity is available when ALL conditions are met:
            1. coordinator.last_update_success is True (coordinator functioning)
            2. coordinator.device is not None (device instance exists)
            3. coordinator.device.is_connected is True (device MQTT connected)

        Note:
            Unavailable entities appear grayed out in Home Assistant UI
            and their states are not updated. This prevents stale data
            from being displayed when devices are offline or coordinators
            are experiencing issues.

            The availability combines both coordinator health (successful
            data updates) and device connectivity (MQTT connection status)
            for comprehensive availability determination.

        Example:
            Entity will be unavailable in these scenarios:

            >>> # Coordinator update failed
            >>> coordinator.last_update_success = False  # → available = False
            >>>
            >>> # Device not initialized
            >>> coordinator.device = None  # → available = False
            >>>
            >>> # Device disconnected from MQTT
            >>> coordinator.device.is_connected = False  # → available = False
        """
        return self.coordinator.last_update_success and (
            self.coordinator.device is not None and self.coordinator.device.is_connected
        )

    def _handle_coordinator_update_safe(self) -> None:
        """Handle coordinator updates with thread safety for MQTT callbacks.

        Ensures coordinator updates are processed in the correct Home Assistant
        event loop context, preventing thread safety issues when MQTT callbacks
        trigger coordinator updates from background threads.

        Thread Safety Strategy:
        1. Check if Home Assistant instance and event loop are available
        2. Use call_soon_threadsafe to schedule update in main thread
        3. Fallback to direct call if hass context unavailable (testing)

        Note:
            MQTT callbacks from paho-mqtt occur in background threads, but
            Home Assistant entity updates must occur in the main event loop.
            This method ensures proper thread context for all updates.

        Example:
            Typical call chain:

            >>> # MQTT callback (background thread)
            >>> device.on_message() → coordinator.async_update_listeners()
            >>> # → entity._handle_coordinator_update_safe() (background thread)
            >>> # → hass.loop.call_soon_threadsafe() (schedules in main thread)
            >>> # → entity._async_handle_coordinator_update() (main thread)
        """
        if self.hass and hasattr(self.hass, "loop"):
            # Use call_soon_threadsafe to schedule the update in the main thread
            def schedule_update():
                """Schedule the async update task."""
                self.hass.async_create_task(self._async_handle_coordinator_update())

            self.hass.loop.call_soon_threadsafe(schedule_update)
        else:
            # Fallback to direct call if hass is not available
            super()._handle_coordinator_update()

    async def _async_handle_coordinator_update(self) -> None:
        """Handle coordinator update in the main Home Assistant event loop.

        Processes coordinator updates in the correct async context,
        ensuring entity state updates occur properly within Home Assistant's
        event loop and entity lifecycle management.

        This method is called from _handle_coordinator_update_safe after
        proper thread context is established via call_soon_threadsafe.

        Process:
        1. Execute in main Home Assistant event loop
        2. Call parent CoordinatorEntity update handling
        3. Trigger entity state updates and UI refreshes
        4. Ensure proper async context for all operations

        Note:
            This is the final step in the thread-safe update chain:
            MQTT callback → coordinator update → thread-safe scheduling →
            this async method → entity state update → UI refresh
        """
        super()._handle_coordinator_update()
