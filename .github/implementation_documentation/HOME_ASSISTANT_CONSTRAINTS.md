# Home Assistant Dependency Constraints

This document tracks Home Assistant's dependency constraints that affect this integration.

## Cryptography Version Tracking

Home Assistant pins certain dependencies to specific versions for stability and security. We follow these constraints to ensure compatibility.

### Current Constraints

| Dependency    | HA Version | HA Constraint | Our Constraint | Last Updated |
|---------------|------------|---------------|----------------|--------------|
| cryptography  | 2025.8.0+  | ==45.0.3      | >=45.0.3 <46.0.0 | 2025-09-27 |

### How to Update Constraints

When Home Assistant updates their cryptography pin:

1. **Check HA's current requirements**:
   - Visit: https://github.com/home-assistant/core/blob/dev/requirements.txt
   - Or check a specific HA release requirements

2. **Update renovate.json**:
   - Find the "Cryptography - version range follows Home Assistant compatibility" rule
   - Update the `allowedVersions` field to match HA's new constraint range
   - Example: If HA updates to `cryptography==46.0.0`, change to `"allowedVersions": ">=46.0.0 <47.0.0"`

3. **Update requirements.txt**:
   - Update the cryptography version to match HA's minimum requirement
   - Use exact pin (`==`) or minimum (`>=`) based on your preference

4. **Update this table**:
   - Record the new HA version, constraint, and date

### Monitoring Home Assistant Releases

Consider setting up notifications for:
- Home Assistant release notes
- Changes to https://github.com/home-assistant/core/blob/dev/requirements.txt
- Security advisories that might affect shared dependencies

### Example Update Process

When HA 2025.9.0 is released with `cryptography==46.1.0`:

1. Update `renovate.json`:
   ```json
   "allowedVersions": ">=46.1.0 <47.0.0"
   ```

2. Update `requirements.txt`:
   ```
   cryptography>=46.1.0
   ```

3. Update this table with new HA version and date