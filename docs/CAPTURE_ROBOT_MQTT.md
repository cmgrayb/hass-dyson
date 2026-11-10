# Capturing what your robot vacuum says

New Dyson robots (like the Spot+Scrub RB07) talk to the MyDyson app in ways
the integration has to learn. `scripts/capture_robot_mqtt.py` records that
conversation while you use the app, one control at a time, and saves it as a
single file you can attach to a GitHub issue.

**It only listens.** The script never sends commands to your robot; everything
it records comes from you using the MyDyson app as normal.

## Before you start

- Python 3.10 or newer on a computer (Mac, Windows or Linux).
- Your phone with the MyDyson app, and the robot on its dock.
- In Home Assistant, temporarily disable the Dyson integration
  (**Settings > Devices & services > Dyson > three dots > Disable**) so it
  doesn't share the cloud connection with the script. Turn it back on when
  you're done.
- About 20 minutes. Every step can be skipped.

## Run it

**Mac or Linux** (paste into Terminal):

```bash
python3 -m venv dyson-capture && dyson-capture/bin/pip install -q "libdyson-rest==0.17.2" "paho-mqtt>=2.2" && curl -fsSLO https://raw.githubusercontent.com/FredLiuuuu/hass-dyson/rb07-jdm-parity/scripts/capture_robot_mqtt.py && dyson-capture/bin/python capture_robot_mqtt.py
```

**Windows** (paste into PowerShell):

```powershell
py -m venv dyson-capture; dyson-capture\Scripts\pip install -q "libdyson-rest==0.17.2" "paho-mqtt>=2.2"; curl.exe -fsSLO https://raw.githubusercontent.com/FredLiuuuu/hass-dyson/rb07-jdm-parity/scripts/capture_robot_mqtt.py; dyson-capture\Scripts\python capture_robot_mqtt.py
```

## What happens

1. **Sign in.** Enter the email and password of your MyDyson account, then the
   code Dyson emails you. These go only to Dyson and are never saved.
2. **Connect.** The script finds your robot and asks you to open it in the app
   so it can confirm the robot is talking.
3. **Follow the steps.** You'll see prompts like:

   ```
   Step 6 of 18: Change one room's cleaning mode
     Open one room's settings and change only its cleaning mode.
     (Do this while the robot is on its dock.)
     Press Enter when you've done it (s = skip, q = finish now):
   ```

   Do it in the app, press Enter, and the script listens for ten seconds for
   the robot's reply. Type `s` to skip anything your robot doesn't have, or
   `q` to stop early; what you've done so far is kept.
4. **Anything else.** The last step lets you name and record any extra buttons
   your model has.

## What to send back

At the end the script prints the file name, for example
`dyson_RB07_capture_20261111-1030.txt`, saved in the folder you ran it from.
Drag that file into a comment on the GitHub issue.

Your serial number, passwords, tokens and Wi-Fi details are removed from the
file. Room names and map positions are kept, because the integration needs
them; open the file in any text editor if you'd like to check it first.

## Troubleshooting

- **"Signing in didn't work"**: check the code hasn't expired and that the
  country code matches your MyDyson account (for example `GB`, `US`, `AU`).
- **"The robot hasn't sent anything yet"**: make sure the robot shows as
  online in the app and the Home Assistant integration is disabled, then
  carry on; messages often start once you use a control.
- **Connection dropped messages**: these usually recover on their own within
  a few seconds. If they keep repeating, check Home Assistant isn't still
  connected to the robot.
