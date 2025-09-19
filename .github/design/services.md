# Home Assistant Services

## Cloud Device Discovery

This service should only be added if a cloud account has been defined

This service serves two functions:

- Returning all of the necessary information from a cloud hub which is required to add a device manually
    - A selection for which cloud hub to use should be included with the first account found automatically populated to ensure multiple account support
- Returning missing feature data to an issue

The first function should be the default function for the service
The second function should require a checkbox to remove sensitive information to make the data safe to post publicly.  When this checkmark is selected, the service should return:

- MQTT Topic
- Device Category
- Device Capabilities

In both cases, the service should return a list of all devices on the account selected with the appropriate level of information.

When writing the service, ensure that matching code coverage tests are created at the same time to maintain our coverage level.