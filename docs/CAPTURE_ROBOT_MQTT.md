# Recording what your robot vacuum says

New Dyson robots (like the Spot+Scrub RB07) talk to the MyDyson app in ways
the integration has to learn. You can help by turning on the integration's
debug log, using each control in the MyDyson app once, and sharing the log.

Turning on the log doesn't change what the integration sends to the robot.
Everything it records comes from you using the app as normal.

## Before you start

- The robot is set up in the Dyson integration and on its dock, charged.
- Your phone with the MyDyson app.
- About 20 minutes. Skip anything your robot doesn't have.

## 1. Turn on debug logging

In Home Assistant, go to **Settings > Devices & services > Dyson**, open the
three-dot menu and choose **Enable debug logging**.

## 2. Work through the checklist

Copy this list into a note or straight into your GitHub comment. For each
step, write down the time you did it, then **wait about 15 seconds** before
the next one so the robot's replies don't overlap. Skip anything that
doesn't apply and mark it "skipped".

```
Time   Step
       1. Leave the robot alone for 1 minute (baseline)
       2. Open the robot in the MyDyson app and wait for the map to load
       3. Change the whole-home cleaning mode (e.g. vacuum and mop -> vacuum only)
       4. Change the whole-home suction / power level
       5. Change the water / hydration level
       6. Open one room's settings and change only its cleaning mode
       7. Same room: change only its suction / power level
       8. Same room: change its water level or number of mop passes
       9. Put that room's settings back how they were
      10. Start a whole-home clean, let it run for a minute
      11. Pause the clean
      12. Resume it for about 30 seconds
      13. Send the robot back to the dock and wait until it docks
      14. Clean a single room for a minute, then send it home
      15. Dock actions, if your app has them (empty bin, wash or dry pads)
      16. Rename one room, then change the name back
      17. Create a schedule, then delete it
      18. Anything else your RB07 has (name each one and its time)
```

Steps 3 to 9, 15 and 16 work best while the robot is on its dock.

## 3. Download the log

Go back to **Settings > Devices & services > Dyson** and choose **Disable
debug logging** from the three-dot menu. Your browser downloads the log file
straight away.

## 4. Check it and share it

Every robot message is on a line containing `MQTT RX`, with the serial
number masked. Passwords and tokens are masked too.

Before you post, open the file in a text editor and search for your serial
number (it's on the robot's label and in the app under the robot's details)
and your email address. Replace any you find with `SERIAL` or `EMAIL`.

Then drag the log file and your filled-in checklist into a comment on the
GitHub issue. If the file is over 25 MB, zip it first.
