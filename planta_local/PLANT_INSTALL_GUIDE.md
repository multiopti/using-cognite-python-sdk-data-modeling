# Plant install guide: Streamlit server (planta_local)

Use this guide on site to install the plant's Streamlit server on a Windows PC. It covers:

- **Before the visit:** what to prepare at the office.
- **At the plant:** steps 1 to 7, in order.
- **Day-to-day operation**, troubleshooting, and rollback.

Do the Optix deploy and the Node-RED flow import first. Both are covered in `E:\source\repos\streamlit\node-red\plant_visit_checklist.md`. The Streamlit server only reads from Node-RED, so it can't be tested until Node-RED returns the 119 matrices.

```
FT Optix Edge (10.86.193.3:59100) --OPC UA--> Node-RED (:1880) --HTTP /api/data_week--> Streamlit server (:8500-8503)
```

| What | Address | For |
|---|---|---|
| TV rotation of Línea 1 / Línea 3 | `http://<server>:8500/tv.html` | Plant TV |
| Línea 1 - Vista de Planta | `http://<server>:8501` | Anyone |
| Línea 3 - Vista de Planta | `http://<server>:8502` | Anyone |
| Reporte de Producción | `http://<server>:8503` | Operators. **Anyone who can open the page can edit incidents.** |

---

## 0. Before the visit (at the office)

- [ ] **Branch:** `git pull` on the `planta-local-nodered` branch. It needs commit `8b27715` or later, which removed cognite-sdk from the server.
- [ ] **Copy the files to a USB stick.** Only these folders from `cognite-sdk` are needed, and they must keep the same structure:
  ```
  cognite-sdk\
    planta_local\                         (without .venv\, logs\, __pycache__\)
    streamlit\                            Reporte de Producción app
    linea1_plant_view\
    linea3_plant_view\
    functions\hourly_production_report\   (formula constants; only config.py is read)
  ```
  **Do not copy `.env`.** It holds the CDF credentials and the plant server doesn't need it.

  PowerShell commands to build the copy, assuming the USB stick is `F:`:
  ```powershell
  $src = "E:\source\repos\streamlit\cognite-sdk"; $dst = "F:\planta\cognite-sdk"
  foreach ($d in "planta_local","streamlit","linea1_plant_view","linea3_plant_view","functions\hourly_production_report") {
      robocopy "$src\$d" "$dst\$d" /E /XD .venv logs __pycache__ /XF .env *.pyc
  }
  ```
- [ ] **Python installer** for Windows 64-bit, version 3.12 recommended (3.11 or later works), from https://www.python.org/downloads/windows/. Take it on the USB stick.
- [ ] **Offline packages, in case the plant PC has no internet.** Run this on a PC with internet. Use the same Python version you'll install at the plant:
  ```powershell
  cd F:\planta\cognite-sdk\planta_local
  py -3.12 -m pip download -r requirements.txt -d wheels --only-binary=:all: --platform win_amd64 --python-version 3.12
  py -3.12 -m pip download pip -d wheels --only-binary=:all:
  ```
  The `wheels\` folder (about 100 MB) goes inside `planta_local\` on the USB stick.
- [ ] **Ask plant IT** for:
  - which PC will host the server;
  - an administrator account on it;
  - a fixed IP, or a DHCP reservation, so the addresses don't change.

## 1. Check the target PC

- [ ] Windows 10/11 or Windows Server, powered on permanently, on the plant network.
- [ ] **Node-RED is reachable from this PC.** Open the following URL in a browser on that PC:
  - `http://127.0.0.1:1880/api/data_week` if Node-RED runs on the same PC;
  - `http://<nodered-ip>:1880/api/data_week` if it runs on another PC.

  It must return JSON with **119 keys** (87 production + 32 `*_OBS`). PowerShell check:
  ```powershell
  (Invoke-RestMethod http://127.0.0.1:1880/api/data_week).data_week.PSObject.Properties.Name.Count
  ```
- [ ] **Ports 8500–8503 are free:**
  ```powershell
  Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8500..8503
  ```
  This must print nothing. If something is listening, change the ports in `planta_server.py` (`TV_PORT`, `APPS`) and in `install_service.ps1`, which has a firewall rule for 8500-8503.

## 2. Install Python

- [ ] Run the installer and tick **"Add python.exe to PATH"**. The default "Install Now" also installs the `py` launcher.
- [ ] Open a **new** PowerShell window and check:
  ```powershell
  py -3 --version     # or: python --version   -> 3.11 or later
  ```

## 3. Copy the files

- [ ] Copy `F:\planta\cognite-sdk` to **`C:\planta\cognite-sdk`**. Use a local folder, not the user's Desktop or Documents: the server runs as the SYSTEM account at startup and must be able to read it.
- [ ] **Only if Node-RED is NOT on this PC:** edit `C:\planta\cognite-sdk\planta_local\planta_server.py` and change:
  ```python
  NODERED_URL = "http://<nodered-ip>:1880"
  ```
- [ ] Leave `DATA_SOURCE = "nodered"`. With it the Reporte is editable, and the server needs neither `.env` nor internet.

## 4. Install the service

Open PowerShell **as Administrator**. Right-click it and choose "Run as administrator".

**With internet:**
```powershell
cd C:\planta\cognite-sdk
powershell -ExecutionPolicy Bypass -File planta_local\install_service.ps1
```

**Without internet** (using the `wheels\` folder from step 0):
```powershell
cd C:\planta\cognite-sdk
$env:PIP_NO_INDEX = "1"
$env:PIP_FIND_LINKS = "C:\planta\cognite-sdk\planta_local\wheels"
powershell -ExecutionPolicy Bypass -File planta_local\install_service.ps1
```

The script:
1. creates `planta_local\.venv` and installs the packages;
2. opens ports 8500–8503 in the firewall for the domain and private profiles;
3. registers the scheduled task **"Planta - Servidor Streamlit"**, which runs as SYSTEM at startup, restarts every minute if it stops, and runs even when no one is logged in;
4. starts the task and prints the 4 addresses with this PC's IP.

**Write down the IP it prints:** `________________`

> **Firewall note:** the rule covers the *Domain* and *Private* profiles. If the plant network is classified as *Public*, check `Get-NetConnectionProfile`. Either ask IT to change it, or run `Set-NetFirewallRule -DisplayName "Planta Streamlit" -Profile Any`.

## 5. Automatic start after power-on

The install script already registers the server to start at boot. It runs as the scheduled task **"Planta - Servidor Streamlit"** under the SYSTEM account, so **no one needs to log in**. If it stops, it restarts every minute. For it to work after a power cut or a shutdown, the PC itself must come back on and do a full boot.

**5.1 Check the scheduled task.** Run as Administrator:
```powershell
$t = Get-ScheduledTask "Planta - Servidor Streamlit"
$t.Triggers | Select-Object CimClass            # must show MSFT_TaskBootTrigger (= "At startup")
$t.Principal | Select-Object UserId, RunLevel   # SYSTEM, Highest
$t.Settings | Select-Object RestartCount, RestartInterval, ExecutionTimeLimit   # 999, PT1M, PT0S
Get-ScheduledTaskInfo "Planta - Servidor Streamlit" | Select-Object LastRunTime, LastTaskResult
```
`LastTaskResult` = `267009` means it is running right now; `0` means it finished. If the task is missing, run `install_service.ps1` again. It is safe to repeat.

**5.2 Turn on the PC automatically when power returns.** Without this, the PC stays off after a power cut until someone presses the button.
- [ ] Enter the BIOS/UEFI: restart and press **F2**, **Del**, **F10** or **F1**, depending on the brand.
- [ ] Look under *Power Management*, *Advanced* or *Chipset* for:
  - **"Restore on AC Power Loss"**, **"AC Recovery"**, **"After Power Failure"** or **"AC Back"**: set it to **Power On** or **Last State**. Power On is preferred.
  - On Dell: *Power Management* → **AC Recovery** = *Power On*.
  - On HP: *Advanced* → *Boot Options* → **After Power Loss** = *On*.
  - On Lenovo: *Power* → **After Power Loss** = *Power On*.
- [ ] Save and exit (usually F10).
- [ ] If the PC is on a UPS, check it also switches the PC back on when power returns.

**5.3 Windows power settings.** Run as Administrator:
```powershell
powercfg /h off                              # disables hibernation AND "Fast startup"
powercfg /change standby-timeout-ac 0        # never sleep
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0        # optional: only matters if this PC also drives a screen
```
**Why turn off Fast startup:** with it on, a Windows "Shut down" is really a partial hibernation, and "At startup" tasks may not run on the next power-on. A Restart is always a full boot.

**5.4 Network ready at startup.** Nothing to do. If the server starts before the network or Node-RED is up, the apps show an error at first and recover on their own: the data is read again every 60 seconds, and the server restarts any app that stops. Node-RED must also start on its own on its PC (service or startup task); check it in the same power test below.

**5.5 Test it with a real power cut:**
- [ ] With the server running, **unplug the PC**, or switch off its breaker or UPS output, and wait 10 seconds.
- [ ] Restore power. Don't touch the keyboard and don't log in.
- [ ] After 2–3 minutes, open `http://<ip>:8501` and `http://<ip>:8503` from another PC. They must load.
- [ ] `planta_local\logs\planta_server.log` shows new "starting ..." lines with the time of the power-on.
- [ ] Also test a normal *Start → Shut down*, then press the power button. It must come back the same way.

**If the scheduled task can't be used** (for example, an IT policy), create it by hand in Task Scheduler (`taskschd.msc` → *Create Task...*):
- *General*:
  - Name: `Planta - Servidor Streamlit`;
  - *Change User or Group* → `SYSTEM`;
  - tick *Run with highest privileges*.
- *Triggers*: *New* → *Begin the task*: **At startup**.
- *Actions*: *New* → *Start a program*:
  - Program: `C:\planta\cognite-sdk\planta_local\.venv\Scripts\python.exe`
  - Arguments: `"C:\planta\cognite-sdk\planta_local\planta_server.py"`
  - Start in: `C:\planta\cognite-sdk`
- *Conditions*: untick *Start the task only if the computer is on AC power*.
- *Settings*:
  - tick *Run task as soon as possible after a scheduled start is missed*;
  - *If the task fails, restart every* **1 minute**, *up to* **999** times;
  - untick *Stop the task if it runs longer than*.

## 6. Verify

Wait 1–2 minutes after the install finishes.

**On the server itself:**
- [ ] The task is running:
  ```powershell
  Get-ScheduledTask "Planta - Servidor Streamlit" | Select-Object State     # Running
  ```
- [ ] The ports are listening:
  ```powershell
  Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8500..8503 | Select-Object LocalPort
  ```
- [ ] The logs show no errors. Check `C:\planta\cognite-sdk\planta_local\logs\`:
  - `planta_server.log` should show "starting ... on :8501/8502/8503" and "TV page on :8500";
  - `linea1_plant_view.log`, `linea3_plant_view.log` and `streamlit.log` should have no tracebacks.

**From another PC on the network** (an operator PC or a phone on the plant Wi-Fi):
- [ ] `http://<ip>:8501`: Línea 1 shows the machines with values. Values from the current hour appear when the hour ends, at minute 59.
- [ ] `http://<ip>:8502`: same check for Línea 3.
- [ ] `http://<ip>:8503`: Reporte de Producción.
  - [ ] Choose yesterday, a machine and a shift. The hourly table appears.
  - [ ] The footer reads "Node-RED: datos leídos <date time> (119 matrices)" in normal colour. Red means the last read is older than 15 minutes or failed.
  - [ ] The **"Guardar Cambios 💾"** button is visible, and there is no "Modo Vista" notice.
  - [ ] **Incident test:**
    1. In "Observaciones / Incidencias", set one hour that has already finished to an incident and save. The page must say "registro(s) actualizados correctamente".
    2. Press "Actualizar 🔄". The incident must still be there.
    3. Restore it to the automatic text and save. If you want to check it in Optix, look at `Model/OBSERVACIONES/<machine>_OBS_DATA_WEEK`.
  - [ ] An hour that hasn't finished yet must be **refused** with "todavía no termina".
- [ ] `http://<ip>:8500/tv.html`: alternates between Línea 1 and Línea 3 every 30 seconds.
- [ ] Power-on test done (step 5.5): everything comes back by itself, with no one logged in.

## 7. Plant TV

- **Mini-PC connected over HDMI (recommended):**
  1. Press Win+R, type `shell:startup` and press Enter.
  2. Create a shortcut there with this target:
     ```
     "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk "http://<ip>:8500/tv.html" --edge-kiosk-type=fullscreen --no-first-run
     ```
  3. Set Windows to log in automatically and turn off sleep and the screen saver.
- **Smart TV with a browser:** open `http://<ip>:8500/tv.html` in full screen. If the views don't load inside the page, use a mini-PC.
- **Options** you can add to the address:
  - `?s=45`: seconds per view;
  - `?ports=8501,8502,8503`: which apps to rotate;
  - `?vh=1250`: virtual height of each view.

---

## Day-to-day operation

**Restart the server**, for example after editing `planta_server.py`. Run as Administrator:
```powershell
Stop-ScheduledTask "Planta - Servidor Streamlit"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "planta_server.py|run_app.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask "Planta - Servidor Streamlit"
```
Stopping the task doesn't always close the Streamlit processes. If they're left running they keep the ports busy, which is why the middle step closes them.

**Run by hand from a terminal**, to watch errors live. Stop the task first, using the commands above without the last line. Then run:
```powershell
cd C:\planta\cognite-sdk
planta_local\.venv\Scripts\python.exe planta_local\planta_server.py
```
Press Ctrl+C to stop it. Then start the task again with `Start-ScheduledTask "Planta - Servidor Streamlit"`.

**Settings in `planta_server.py`:**

| Setting | Default | Meaning |
|---|---|---|
| `NODERED_URL` | `http://127.0.0.1:1880` | Where Node-RED is |
| `REFRESH_S` | 60 | Seconds between data refreshes |
| `APPS` | Reporte `False` | Third value `True` makes that app read-only. For example, set the Reporte to `True` to stop operators from editing incidents. |
| `DATA_SOURCE` | `"nodered"` | Leave as is. `"cdf"` needs cognite-sdk, `.env` and internet, and makes the Reporte read-only. |

**Incident list:** it lives in `streamlit\config.py` (`INCIDENTES_OPCIONES`). **Only add new options at the end**, because Optix stores the position in the list. After changing it, restart the server.

## Troubleshooting

| Symptom | Check |
|---|---|
| No address opens from other PCs | Run `Get-ScheduledTask "Planta - Servidor Streamlit"` and confirm it is Running. Check the ports are listening. Check the firewall profile (see the note in step 4). Check that the server's IP hasn't changed. |
| Address opens on the server but not on other PCs | Firewall or network profile, see step 4. |
| An app shows an error | Check `planta_local\logs\<app>.log`. Usually Node-RED isn't answering at `NODERED_URL`: open `http://<nodered>:1880/api/data_week`. |
| Red footer in the Reporte | Node-RED isn't answering or failed its last read. Check the Node-RED service and its OPC UA connection to Optix. |
| `/api/data_week` returns fewer than 119 keys | The Optix project is missing the D&I/Minster or `OBSERVACIONES` matrices: it wasn't deployed. Or Node-RED has no OPC UA session; see the session-limit item in the checklist. |
| Values show N/A or are empty | Optix isn't getting data from the PLC (power cut, network or PLC fault). The apps correctly show what is in the Optix matrices. |
| Saving an incident fails | The Reporte names the hours that failed. Check that Node-RED answers `POST /api/observacion` and that its write client is connected to Optix. |
| Install fails at `pip install` | No internet: use the offline procedure in step 4. If it says no matching distribution was found, the wheels were downloaded for a different Python version than the one installed. |
| `Ejecuta este script como Administrador` | Open PowerShell with "Run as administrator". |

## Uninstall / rollback

Run as Administrator:
```powershell
cd C:\planta\cognite-sdk
powershell -ExecutionPolicy Bypass -File planta_local\uninstall_service.ps1
```
This removes the scheduled task and the firewall rule, and stops the processes. It doesn't touch Optix or Node-RED. Delete `C:\planta` by hand if it's no longer needed.
