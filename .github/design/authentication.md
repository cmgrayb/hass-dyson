# Authentication

This file documents the expectations for authentication to Dyson products

## API Authentication

Before any device can be communicated with, we must fetch the credentials to connect to the device via Dyson's cloud API.

The cloud API should be interacted with through existing methods in libdyson-rest as a dependency.

Authentication to the API is performed through a multifactor series of steps, requiring the user to first provide their email address and credentials, then to respond to a prompt for a 6-digit numeric code emailed to them

## Local Device Authentication

Local devices have an onboard MQTT broker with a preexisting password not readily available to the end user.  The username and password to the device may be determined through an existing function in libdyson-rest.

## IoT Authentication

Less is known about the IoT connectivity.  It appears to be an MQTT broker proxy hosted in cloud by Dyson.
Connection information including an encoded, encrypted, and/or hashed password may be determined through an existing function in libdyson-rest.  It is believed that we do not have to know the original value of the IoT password and may pass it to the broker as-is, however, that may be checked against known functional code found at <https://github.com/libdyson-wg/opendyson>.