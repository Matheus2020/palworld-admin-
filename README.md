# Palworld Dedicated Server Tools

## Feature Roadmap
<details open>
  <summary><b>Server Manager:<b></summary>
<details open>
  <summary>🟢 1-Click Installer</summary>
- 🟢 Windows<br>
- 🟢 Linux  
</details>
<details open>
  <summary>🟢 1-Click Launcher</summary>
- 🟢 Windows<br>
- 🟢 Linux  
</details>
<details open>
  <summary>🟡 Data Backup & Restore</summary>
- 🟢 Manually Backup Server Data<br>
- ⚪ Automatically Backup Server Data<br>
- ⚪ AutoPrune Server Data (by quantity)<br>
- ⚪ Restore Server Data from Backup<br>
</details>
<details open>
  <summary>⚪ Server Auto Restart</summary>
- ⚪ Schedule Based<br>
- ⚪ RAM Utilization Based<br>
</details>
</details>

<details open>
  <summary>🟢 RCON Client:</summary>
- 🟢 Connect<br>
- 🟢 Broadcast Message (Multi Word working)<br>
- 🟢 List Players<br>
- 🟢 View SteamID/UID<br>
- 🟢 Kick Players<br>
- 🟢 Ban Players<br>
- 🟢 Save Game<br>
- 🟢 Shutdown Gracefully
</details>

<details open>
  <summary>🟡 Server Settings Manager:</summary>
  <details open>
    <summary>🟢 Generate Settings:</summary>
    - 🟢 PalWorldSettings.ini<br>
    - 🟢 WorldOption.sav
  </details>
  <details open>
    <summary>⚪ Read/Write Directly to Server:</summary>
  - ⚪ Read settings directly from server<br>
  - ⚪ Write settings directly to server<br>
  - ⚪ Server Profile Manager (Store different settings that can be easily swapped)
  </details>
</details>

<details open>
  <summary>⚪Beyond RCON</summary>
- ⚪ Whitelist Player<br>
- ⚪ Whitelist Mode (Only allow whitelisted players to join server)<br>
- ⚪ Unban Player<br>
- ⚪ Broadcast player joins in server<br>
- ⚪ Create RCON Log<br>
- ⚪ display HEX UID for easy Save Identification
</details>

## **To access the Remote Server Manager:**
- Run the binary on your host, make sure port 8210 is open and forwarded
- Access it with your browser of choice by navigating to http://[HOSTIP]:8210

_Use palworld-servertools binary after `chmod + x`_
_Make sure to use `-r -mp [management password]` when launching remote management on  Linux_

**Important:**
The remote manager does not have RCON built in. You still want to use the windows version to access the server managed in Linux via RCON

## How to run directly from the code:
- Install python, at least 3.11
- Install poetry `pip install poetry` make sure you add it to your PATH
- Download the code to a directory
- From that directory run `poetry install`
- Then run `poetry run python main.py`
- Profit

## How to transition from an existing server:
- **MAKE A BACKUP**
- Download the newest version of the app
- Go to Local Server Manager in the main menu
- Click `Install | Update` > `Confirm` > Wait for it to finish
- Go to your backup and copy the directory:
`steamapps/common/PalServer/Pal/Saved` **FROM** your backup and overwrite that same directory inside the steamcmd that my app creates
- Restart the app > Local Server Manager
- You should now see the existing options of your server
- Modify them as needed, including adding an Admin Password (this is the RCON password as well)
- Click the button to update settings (This will save the changes)
- Click Start Server, take note of the Local IP / RCON port / Admin Pass
- Switch to RCON window
- Enter the Local IP / RCON port / Admin
- Click Connect
You should now be connected to the server via RCON

![image](https://github.com/Lukium/palworld-servertools/assets/99280463/75f144d2-e3d7-413b-a357-c25e38488421)
![image](https://github.com/Lukium/palworld-servertools/assets/99280463/502ebcde-422b-444b-8574-d360b5e3c577)
![image](https://github.com/Lukium/palworld-servertools/assets/99280463/be2c08c7-6c8c-4324-97fc-30732157f893)

## Troubleshooting:
If you are running a non-standard version of windows (for example, Remote/Virtual Environment, Windows Server) you will likely need to install the Webview2 runtime from Microsoft, which can be found [here](https://developer.microsoft.com/en-us/microsoft-edge/webview2/?form=MA13LH#download)
You will know this is the case if upon opening the app, it looks like either of the following screenshots:<br>
![image](https://github.com/Lukium/palworld-servertools/assets/99280463/582eac35-40f5-4a17-abec-55da4389a356)
![image](https://github.com/Lukium/palworld-servertools/assets/99280463/2f0d585e-af54-4236-9426-7cf36fee7c90)



Credits:

- https://github.com/cheahjs/palworld-save-tools (Expanded and Modified)

- https://github.com/itzg/rcon-cli (Expanded, Modified, Translated to Python)
