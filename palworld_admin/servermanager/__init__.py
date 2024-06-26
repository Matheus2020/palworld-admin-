"""Server Manager module for PalWorld Admin."""

from datetime import datetime
import filecmp
import json
import logging
import os
import re
import shutil
import subprocess
import time
import zipfile

import requests

from palworld_admin.converter.convert import convert_json_to_sav
from palworld_admin.helper.dbmanagement import save_user_settings_to_db
from palworld_admin.helper.fileprocessing import file_to_lines, extract_file
from palworld_admin.helper.networking import (
    get_public_ip,
    get_local_ip,
    download_file,
)

from palworld_admin.settings import app_settings


def check_os() -> dict:
    """Check the OS."""
    result = {}
    os_name = app_settings.app_os
    result["status"] = "success"
    result["value"] = f"{os_name}"
    return result


def check_steamcmd_install() -> dict:
    """Check if steamcmd is installed."""
    result = {}
    # Check if steamcmd is installed
    try:
        if os.path.isfile(app_settings.localserver.steamcmd_path):
            result["status"] = "success"
            result["value"] = True
            app_settings.localserver.steamcmd_installed = True
        else:
            result["status"] = "success"
            result["value"] = False
            app_settings.localserver.steamcmd_installed = False
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = f"Error checking SteamCMD installation: {e}"
    return result


def check_palworld_install() -> dict:
    """Check if PalWorld is installed."""
    result = {}
    # Check if PalWorld is installed
    try:
        if os.path.isfile(app_settings.localserver.ini_path):
            # Check if the file is not empty by reading the file and checking for content
            with open(
                app_settings.localserver.ini_path, "r", encoding="utf-8"
            ) as file:
                file_content = file.read()
            # Remove leading and trailing whitespace
            file_content = file_content.strip()
            if len(file_content) > 0:
                result["status"] = "success"
                result["value"] = True
                app_settings.localserver.palserver_installed = True
            else:
                result["status"] = "success"
                result["value"] = False
        else:
            result["status"] = "success"
            result["value"] = False
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = f"Error checking PalWorld installation: {e}"
    return result


def check_palguard_install() -> dict:
    """Check if PalGuard is installed."""
    result = {}
    # Check if PalGuard is installed
    palguard_path = os.path.join(
        app_settings.localserver.binaries_path, "palguard.dll"
    )
    try:
        if os.path.isfile(palguard_path):
            result["status"] = "success"
            result["value"] = True
            app_settings.localserver.palguard_installed = True
        else:
            result["status"] = "success"
            result["value"] = False
            app_settings.localserver.palguard_installed = False
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = f"Error checking PalGuard installation: {e}"
    return result


def check_world_sav_exists() -> dict:
    """Check if the world.sav file exists."""
    result = {}
    target = os.path.join(app_settings.localserver.sav_path, "WorldOption.sav")
    try:
        if os.path.isfile(target):
            result["status"] = "success"
            result["value"] = True
        else:
            result["status"] = "success"
            result["value"] = False
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = f"Error checking WorldOption.sav existence: {e}"
    return result


def read_server_settings():
    """Read and parse server settings from the settings file, handling special cases."""
    result = {}
    logging.info(
        "Reading settings file from %s", app_settings.localserver.ini_path
    )
    try:
        with open(
            app_settings.localserver.ini_path, "r", encoding="utf-8"
        ) as file:
            content = file.read()
            result["status"] = "success"
            result["value"] = content
            logging.info("Read settings file successfully.")
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = "Error reading settings file"
        logging.error("Error reading settings file: %s", e)
        return result

    # Extract the settings from the settings file
    try:
        settings_start = content.find("OptionSettings=(") + len(
            "OptionSettings=("
        )
        settings_end = content.rfind(")")  # Find the last ')' in the content
        settings_string = content[settings_start:settings_end]

        pattern = re.compile(r'(\w+)=("[^"]*"|[^,]*)')
        settings = pattern.findall(settings_string)

        settings_dict = {
            key.strip(): value.strip('"') for key, value in settings
        }
        result["status"] = "success"
        result["settings"] = settings_dict

        # Get the local IP address
        local_ip = get_local_ip()
        if not local_ip:
            result["status"] = "error"
            result["message"] = "Error getting local IP address"
        else:
            result["settings"]["LocalIP"] = local_ip

        app_settings.localserver.server_settings = settings_dict

    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["value"] = "Error processing settings file"
        logging.error("Error processing settings file: %s", e)

    return result


def check_install() -> dict:
    """Check if steamcmd is installed."""
    log = False
    result = {}  # Final result to be returned

    # Check Installation
    os_result = check_os()
    steamcmd_result = check_steamcmd_install()
    palserver_result = check_palworld_install()

    if (
        os_result["status"] == "success"
        and steamcmd_result["status"] == "success"
        and palserver_result["status"] == "success"
    ):
        # Combine the results
        result["status"] = "success"
        result["os"] = os_result
        result["steamcmd"] = steamcmd_result
        result["palserver"] = palserver_result

        # If both SteamCMD and PalServer are installed, read the settings
        if (
            steamcmd_result["value"] is True
            and palserver_result["value"] is True
        ):
            logging.info(
                "SteamCMD and PalServer are installed, reading settings."
            )
            result_settings = read_server_settings()
            result["settings"] = result_settings["settings"]
            result["world_options_sav"] = check_world_sav_exists()

        if log:
            logging.info("Installation check result: %s", result)
    else:
        result["status"] = "error"
        result["message"] = "Error checking installation"
        logging.info("Error checking installation: %s", result)
    return result


def install_steamcmd() -> dict:
    """Install steamcmd."""
    result = {}
    if app_settings.app_os == "Windows":
        try:
            # Use Powershell to Download steamcmd from
            # https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip
            logging.info("Downloading steamcmd.zip")
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Invoke-WebRequest -Uri https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -OutFile steamcmd.zip",  # pylint: disable=line-too-long
                ],
                check=True,
            )
            logging.info("Download complete.")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error downloading steamcmd.zip"
            logging.info("Error downloading steamcmd.zip: %s", e)
            return result
        # Unzip steamcmd.zip to steamcmd folder
        try:
            with zipfile.ZipFile("steamcmd.zip", "r") as zip_ref:
                zip_ref.extractall("steamcmd")
            logging.info("Unzip complete.")
        except Exception as e:  # pylint: disable=broad-except
            result["status"] = "error"
            result["message"] = "Error unzipping steamcmd.zip"
            logging.info("Error unzipping steamcmd.zip: %s", e)
            return result

        # Remove steamcmd.zip
        try:
            os.remove("steamcmd.zip")
            logging.info("Removed steamcmd.zip")
        except Exception as e:  # pylint: disable=broad-except
            result["status"] = "error"
            result["message"] = "Error removing steamcmd.zip"
            logging.info("Error removing steamcmd.zip: %s", e)
            return result

        result["status"] = "success"
        result["message"] = "SteamCMD installed successfully"
        return result
    elif app_settings.app_os == "Wine":
        # Set the base path to the WINEPREFIX/drive_c folder
        base_path = os.path.join(os.environ["WINEPREFIX"], "drive_c")
        steamcmd_path = app_settings.localserver.steamcmd_path

        # Try to download steamcmd.zip
        try:
            logging.info("Downloading steamcmd.zip")
            subprocess.run(
                [
                    "wget",
                    "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
                ],
                check=True,
                cwd=base_path,
            )
            logging.info("Download complete.")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error downloading steamcmd.zip"
            logging.info("Error downloading steamcmd.zip: %s", e)
            return result

        # Unzip steamcmd.zip to steamcmd folder using zipfile
        try:
            with zipfile.ZipFile(
                os.path.join(base_path, "steamcmd.zip"), "r"
            ) as zip_ref:
                zip_ref.extractall(os.path.join(base_path, "steamcmd"))
            logging.info("Unzip complete.")
            # Remove steamcmd.zip
            os.remove(os.path.join(base_path, "steamcmd.zip"))
        except Exception as e:  # pylint: disable=broad-except
            result["status"] = "error"
            result["message"] = "Error unzipping steamcmd.zip"
            logging.info("Error unzipping steamcmd.zip: %s", e)
            return result

        # Verify that steamcmd.exe exists
        if os.path.isfile(steamcmd_path):
            result["status"] = "success"
            result["message"] = "SteamCMD installed successfully"
            return result
    else:  # Linux
        # Same functionality, but for linux
        try:
            logging.info("Installing SteamCMD")
            # Run apt update
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "update",
                    "-y",
                ],
                check=True,
            )
            # Install software-properties-common and debconf-utils
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "install",
                    "software-properties-common",
                    "debconf-utils",
                    "-y",
                ],
                check=True,
            )
            # Add the i386 architecture
            subprocess.run(
                [
                    "sudo",
                    "dpkg",
                    "--add-architecture",
                    "i386",
                ],
                check=True,
            )
            # Accept the SteamCMD EULA
            subprocess.run(
                [
                    "echo",
                    "steamcmd steam/question select I AGREE",
                    "|",
                    "sudo",
                    "debconf-set-selections",
                ],
                check=True,
            )
            # Rerun apt update
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "update",
                    "-y",
                ],
                check=True,
            )
            # Install steamcmd
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "install",
                    "steamcmd",
                    "-y",
                ],
                check=True,
            )
            subprocess.run(
                ["steamcmd", "+exit"],
                check=True,
            )
            result["status"] = "success"
            result["message"] = "SteamCMD installed successfully"
            logging.info("SteamCMD installed successfully")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error installing SteamCMD"
            logging.info("Error installing SteamCMD: %s", e)
        return result


def install_palserver():
    """Install PalServer."""
    result = {}
    if app_settings.app_os == "Windows":
        files_to_copy = [
            "steamclient.dll",
            "steamclient64.dll",
            "tier0_s.dll",
            "tier0_s64.dll",
            "vstdlib_s.dll",
            "vstdlib_s64.dll",
        ]
        try:
            logging.info("Installing PalServer")
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "cd steamcmd; ./steamcmd.exe +login anonymous +app_update 2394010 validate +quit",  # pylint: disable=line-too-long
                ],
                check=True,
            )
            # Copy files_to_copy from app_settings.localserver.main_path to the binaries directory
            for file in files_to_copy:
                shutil.copy(
                    os.path.join(app_settings.localserver.main_path, file),
                    app_settings.localserver.binaries_path,
                )

            result["status"] = "success"
            result["message"] = "PalServer installed successfully"
            logging.info("PalServer installed successfully")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error installing PalServer"
            logging.info("Error installing PalServer: %s", e)
        return result

    elif app_settings.app_os == "Wine":
        # Install PalServer using wine
        steamcmd_path = app_settings.localserver.steamcmd_path

        try:
            logging.info("Installing PalServer")
            subprocess.run(
                [
                    "wine",
                    steamcmd_path,
                    "+login",
                    "anonymous",
                    "+app_update",
                    "2394010",
                    "validate",
                    "+quit",
                ],
                check=True,
            )
            result["status"] = "success"
            result["message"] = "PalServer installed successfully"
            logging.info("PalServer installed successfully")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error installing PalServer"
            logging.info("Error installing PalServer: %s", e)
        return result

    else:
        # Same functionality, but for linux
        home_dir = os.environ["HOME"]
        sdk32_path = os.path.join(home_dir, ".steam/sdk32")
        sdk64_path = os.path.join(home_dir, ".steam/sdk64")
        linux32_path = os.path.join(home_dir, ".steam/steam/steamcmd/linux32")
        linux64_path = os.path.join(home_dir, ".steam/steam/steamcmd/linux64")
        try:
            logging.info("Installing PalServer")
            # Check if sdk directories exist, if not create them using symlinks
            subprocess.run(["echo", home_dir], check=True)
            subprocess.run(["echo", sdk32_path], check=True)
            subprocess.run(["echo", sdk64_path], check=True)
            if not os.path.exists(sdk32_path):
                logging.info("Creating sdk32 symlink")
                subprocess.run(
                    [
                        "ln",
                        "-s",
                        linux32_path,
                        sdk32_path,
                    ],
                    check=True,
                )
            else:
                logging.info("sdk32 symlink already exists")

            if not os.path.exists(sdk64_path):
                logging.info("Creating sdk64 symlink")
                subprocess.run(
                    [
                        "ln",
                        "-s",
                        linux64_path,
                        sdk64_path,
                    ],
                    check=True,
                )
            else:
                logging.info("sdk64 symlink already exists")

            logging.info("Running steamcmd to install PalServer")

            # Run steamcmd to install PalServer
            subprocess.run(
                [
                    "/usr/games/steamcmd",
                    "+login",
                    "anonymous",
                    "+app_update",
                    "2394010",
                    "validate",
                    "+quit",
                ],
                check=True,
            )

            result["status"] = "success"
            result["message"] = "PalServer installed successfully"
            logging.info("PalServer installed successfully")
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error installing PalServer"
            logging.info("Error installing PalServer: %s", e)
        return result


def identify_process_by_name():
    """Identify a process by its executable name."""
    result = {}
    app_settings.localserver.pid = None
    attempts = 0
    max_attempts = 5
    log = True
    if not app_settings.localserver.expected_to_be_running:
        max_attempts = 1
    if app_settings.app_os == "Windows":
        target_path = os.path.join(
            os.getcwd(), app_settings.localserver.binaries_path
        ).replace("/", "\\")
        target_process = app_settings.localserver.executable

        # Check if the use_get_counters flag is set to True
        if app_settings.localserver.use_get_counters:
            # find_cmd = f"powershell \"Get-Process | Where-Object {{ $_.ProcessName -like '*{app_settings.localserver.executable}*' }} | Select-Object Id, Name, MainWindowTitle\""  # pylint: disable=line-too-long
            # find_cmd = f"powershell \"Get-Process | Where-Object {{ $_.ProcessName -like '*{app_settings.localserver.executable}*' }} | ForEach-Object {{ $path = (Get-Item $_.MainModule.FileName).DirectoryName; $_ | Select-Object Id, @{{Name='DirectoryPath'; Expression={{$path}}}} }} \""  # pylint: disable=line-too-long
            # This command will return the Process ID and the counter instance for the Process
            find_cmd = [
                "powershell",
                "-Command",
                rf'$TargetProcess = "{target_process}";',
                rf'$TargetPath = "{target_path}";',
                r'$TargetPID = (Get-Process | Where-Object { $_.ProcessName -like "*$TargetProcess*" } | ForEach-Object { $path = (Get-Item $_.MainModule.FileName).DirectoryName;',  # pylint: disable=line-too-long
                r"if ($path -eq $TargetPath) { $_.Id } });",
                r"$Process = Get-Process -Id $TargetPID;",
                r"$ProcessName = $Process.ProcessName;",
                r'$AllProcesses = Get-Counter "\Process($ProcessName*)\ID Process" -ErrorAction Stop;',
                r"$MatchingInstance = $AllProcesses.CounterSamples | Where-Object { $_.CookedValue -eq $TargetPID };",
                r'$InstanceNameWithSuffix = $MatchingInstance.Path -match "\((.*?)\)" | Out-Null;',
                r"$InstanceNameWithSuffix = $matches[1];"
                r'echo "$TargetPID,$InstanceNameWithSuffix"',
            ]
        # If the use_get_counters flag is set to False, get just the PID to be used with WMI
        else:
            find_cmd = [
                "powershell",
                "-Command",
                rf'$TargetProcess = "{target_process}";',
                rf'$TargetPath = "{target_path}";',
                r'$TargetPID = (Get-Process | Where-Object { $_.ProcessName -like "*$TargetProcess*" } | ForEach-Object { $path = (Get-Item $_.MainModule.FileName).DirectoryName;',  # pylint: disable=line-too-long
                r"if ($path -eq $TargetPath) { $_.Id } });",
                r'echo "$TargetPID"',
            ]

        while not app_settings.localserver.pid:
            try:
                # Find processes
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.run(
                    find_cmd,
                    check=True,
                    startupinfo=startupinfo,
                    capture_output=True,
                    text=True,
                )
                if process.stdout:
                    if log:
                        logging.info(
                            "Process found: %s", process.stdout.strip()
                        )
                    if app_settings.localserver.use_get_counters:
                        matched_pid, instance_result = (
                            process.stdout.strip().split(",")
                        )
                        app_settings.localserver.counters_instance_name = (
                            instance_result
                        )
                        if log:
                            logging.info(
                                "Instance Result: %s", instance_result
                            )
                    else:
                        matched_pid = process.stdout.strip()

                    # matched_pid = None
                    # find_result = process.stdout
                    # own_path = os.path.join(
                    #     os.getcwd(), app_settings.localserver.binaries_path
                    # )
                    # # Replace forward slashes with backslashes
                    # own_path = own_path.replace("/", "\\")

                    # # Drop lines in find_result that don't contain the own_path
                    # matched_result = "\n".join(
                    #     [
                    #         line
                    #         for line in find_result.split("\n")
                    #         if own_path in line
                    #     ]
                    # )

                    # # If matched_result is not empty, extract the PID
                    # if matched_result:
                    #     matched_pid = matched_result.strip().split(
                    #         " ", maxsplit=1
                    #     )[0]

                    # # find_instance = f'powershell "$TargetPID = {matched_pid}; $Process = Get-Process -Id $TargetPID; $ProcessName = $Process.ProcessName; $AllProcesses = Get-Counter "\Process($ProcessName*)\ID Process" -ErrorAction Stop; $MatchingInstance = $AllProcesses.CounterSamples | Where-Object {{ $_.CookedValue -eq $TargetPID }}; echo $MatchingInstance.InstanceName "'
                    # find_instance = f'powershell "$TargetPID = {matched_pid}; $Process = Get-Process -Id $TargetPID; $ProcessName = $Process.ProcessName; $AllProcesses = Get-Counter \\"\\Process($ProcessName*)\\ID Process\\" -ErrorAction Stop; $MatchingInstance = $AllProcesses.CounterSamples | Where-Object {{ $_.CookedValue -eq $TargetPID }}; echo $MatchingInstance.InstanceName"'
                    # #    "'
                    # isntance_process = subprocess.run(
                    #     find_instance,
                    #     check=True,
                    #     shell=True,
                    #     capture_output=True,
                    #     text=True,
                    # )

                    # if isntance_process.stdout:
                    #     instance_result = isntance_process.stdout.strip()
                    #     app_settings.localserver.counters_instance_name = (
                    #         instance_result
                    #     )

                    if log:
                        logging.info("Matched PID: %s", matched_pid)

                    # Extract process IDs
                    # pids = re.findall(
                    #     r"^\s*(\d+)", process.stdout, re.MULTILINE
                    # )
                    # if len(pids) > 0:
                    #     pid = pids[0]
                    if matched_pid:
                        app_settings.localserver.pid = matched_pid
                        app_settings.localserver.running = True
                        result["status"] = "success"
                        result["value"] = matched_pid
                        logging.info("Server Process ID: %s", matched_pid)
                        return result
                    else:
                        result["status"] = "success"
                        result["value"] = "No matching processes found."
                        app_settings.localserver.running = False
                        app_settings.localserver.pid = None
                        logging.info("No matching processes found.")
            except subprocess.CalledProcessError as e:
                info = f"Process not found: {e}"
                logging.error("Error finding process: %s", info)
                result["status"] = "error"
                result["value"] = f"Process not found: {e}"
            attempts += 1
            if attempts > max_attempts:
                result["status"] = "error"
                result["value"] = "Failed to find process"
                break
            if app_settings.localserver.expected_to_be_running:
                logging.info("Attempts to find process: %s/5 failed", attempts)
            time.sleep(1)

    else:
        find_cmd = ["pgrep", "-f", app_settings.localserver.executable]
        while not app_settings.localserver.pid:
            try:
                process = subprocess.run(
                    find_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if process.stdout:
                    # pgrep returns PIDs, one per line. Extract them.
                    pids = process.stdout.strip().split("\n")
                    if len(pids) > 0:
                        pid = pids[0]  # Take the first PID found
                        app_settings.localserver.pid = pid
                        app_settings.localserver.running = True
                        result["status"] = "success"
                        result["value"] = pid
                    else:
                        result["status"] = "success"
                        result["value"] = "No matching processes found."
                        logging.info("No matching processes found.")
            except subprocess.CalledProcessError as e:
                info = f"Failed to execute find command: {e}"
                logging.error(info)
                result["status"] = "error"
                result["value"] = "Failed to find process due to error."
            attempts += 1
            if attempts > max_attempts:
                result["status"] = "error"
                result["value"] = "Failed to find process"
                break
            if app_settings.localserver.expected_to_be_running:
                logging.info("Attempts to find process: %s/5 failed", attempts)
            time.sleep(1)
    return result


def run_server(launcher_args: dict = None):
    """Run the server."""
    result = {}
    log = False

    # Check if the server is already running
    if app_settings.localserver.running:
        result["status"] = "error"
        result["message"] = "Server is already running"
        return result

    # Set the expected_to_be_running flag to True
    app_settings.localserver.expected_to_be_running = True

    if log:
        logging.info("Running server. Launcher Args: %s", launcher_args)
    rcon_port = launcher_args["rcon_port"]
    public_port = launcher_args["public_port"]
    query_port = launcher_args["query_port"]
    useperfthreads = launcher_args["useperfthreads"]
    noasyncloadingthread = launcher_args["NoAsyncLoadingThread"]
    usemultithreadfords = launcher_args["UseMultithreadForDS"]
    launch_rcon = launcher_args["launch_rcon"]
    auto_backup = launcher_args["auto_backup"]
    auto_backup_delay = launcher_args["auto_backup_delay"]
    auto_backup_quantity = launcher_args["auto_backup_quantity"]
    publiclobby = launcher_args["publiclobby"]
    auto_restart_triggers = launcher_args["auto_restart_triggers"]
    auto_restart_on_unexpected_shutdown = launcher_args[
        "auto_restart_on_unexpected_shutdown"
    ]
    ram_restart_trigger = launcher_args["ram_restart_trigger"]

    # Steam Authentication
    steam_auth = launcher_args["steam_auth"]
    enforce_steam_auth_ip = launcher_args["enforce_steam_auth_ip"]
    app_settings.localserver.steam_auth = steam_auth
    app_settings.localserver.enforce_steam_auth_ip = enforce_steam_auth_ip

    # Discord Settings
    discord_bot_enabled = (
        launcher_args["discord_bot_enabled"]
        if launcher_args["discord_bot_enabled"]
        else None
    )
    discord_bot_token = (
        launcher_args["discord_bot_token"]
        if launcher_args["discord_bot_token"]
        else None
    )
    discord_bot_server_id = (
        launcher_args["discord_bot_server_id"]
        if launcher_args["discord_bot_server_id"]
        else None
    )
    discord_bot_channel_id = (
        launcher_args["discord_bot_channel_id"]
        if launcher_args["discord_bot_channel_id"]
        else None
    )
    discord_bot_admin_role_id = (
        launcher_args["discord_bot_admin_role_id"]
        if launcher_args["discord_bot_admin_role_id"]
        else None
    )
    discord_bot_rcon_role_id = (
        launcher_args["discord_bot_rcon_role_id"]
        if launcher_args["discord_bot_rcon_role_id"]
        else None
    )
    discord_bot_rcon_enabled = (
        launcher_args["discord_bot_rcon_enabled"]
        if launcher_args["discord_bot_rcon_enabled"]
        else None
    )
    discord_bot_joins_enabled = (
        launcher_args["discord_bot_joins_enabled"]
        if launcher_args["discord_bot_joins_enabled"]
        else None
    )
    discord_bot_leaves_enabled = (
        launcher_args["discord_bot_leaves_enabled"]
        if launcher_args["discord_bot_leaves_enabled"]
        else None
    )

    app_settings.localserver.discord_bot_enabled = discord_bot_enabled
    app_settings.localserver.discord_bot_token = discord_bot_token
    app_settings.localserver.discord_bot_server_id = discord_bot_server_id
    app_settings.localserver.discord_bot_channel_id = discord_bot_channel_id
    app_settings.localserver.discord_bot_admin_role_id = (
        discord_bot_admin_role_id
    )
    app_settings.localserver.discord_bot_rcon_role_id = (
        discord_bot_rcon_role_id
    )
    app_settings.localserver.discord_bot_rcon_enabled = (
        discord_bot_rcon_enabled
    )
    app_settings.localserver.discord_bot_joins_enabled = (
        discord_bot_joins_enabled
    )
    app_settings.localserver.discord_bot_leaves_enabled = (
        discord_bot_leaves_enabled
    )

    # Construct the command with necessary parameters and flags
    cmd = f'"{app_settings.localserver.launcher_path}"{" -publiclobby" if publiclobby else ""}{f" -port={public_port}"}{f" -RCONPort={rcon_port}"}{f" -queryport={query_port}"}{" -useperfthreads" if useperfthreads else ""}{" -NoAsyncLoadingThread" if noasyncloadingthread else ""}{" -UseMultithreadForDS" if usemultithreadfords else ""}'  # pylint: disable=line-too-long
    # Append "WINEDEBUG=-all wine" if the OS is Wine
    if app_settings.app_os == "Wine":
        cmd = f"WINEDEBUG=-all wine {cmd}"

    try:
        if log:
            logging.info("Starting server with command: %s", cmd)
        # Start the process and return the process object itself
        app_settings.localserver.server_process = subprocess.Popen(
            cmd, shell=True
        )
        identified = identify_process_by_name()
        if log:
            logging.info("Identified: %s", identified)
        if identified["status"] == "success":
            result["status"] = "success"
            result["message"] = "Server started successfully"
            app_settings.localserver.run_auto_backup = auto_backup
            app_settings.localserver.backup_interval = auto_backup_delay
            app_settings.localserver.backup_retain_count = auto_backup_quantity

            app_settings.localserver.auto_restart_monitoring = (
                auto_restart_triggers
            )
            app_settings.localserver.auto_restart_on_unexpected_shutdown = (
                auto_restart_on_unexpected_shutdown
            )
            app_settings.localserver.auto_restart_ram_threshold = (
                ram_restart_trigger
            )

            app_settings.localserver.launch_rcon_on_startup = launch_rcon
            save_user_settings_to_db({"launcher_options": launcher_args})
        else:
            result["status"] = "error"
            result["message"] = "Error starting server"
        logging.info(
            "Palguard installed: %s",
            app_settings.localserver.palguard_installed,
        )
        # app_settings.localserver.running = True
    except Exception as e:  # pylint: disable=broad-except
        if log:
            logging.error("Error starting server: %s", e)
        result["status"] = "error"
        result["message"] = "Error starting server"
    return result


def get_ram_usage_by_pid(pid: int) -> dict:
    """Get the RAM usage by PID."""
    result = {}
    log = False
    if log:
        logging.info("Getting RAM usage by PID: %s", pid)
    if pid:
        ram_cmd = ["ps", "-p", str(pid), "-o", "rss="]
        try:
            process = subprocess.run(
                ram_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            if process.stdout:
                ram_usage = process.stdout.strip()
                if ram_usage == "":
                    ram_usage = "0"
                result["status"] = "success"
                result["value"] = str(round(int(ram_usage) / 1048576, 2))
                if log:
                    logging.info("RAM usage: %s", result)
            else:
                result["status"] = "success"
                result["value"] = "0"
                if log:
                    logging.info("RAM usage: %s", result)
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["value"] = "Error getting RAM usage"
            logging.info("Error getting RAM usage: %s", e)
    return result


def get_cpu_time_by_pid(pid: int) -> dict:
    """Get the CPU time by PID."""
    result = {}
    log = False
    if log:
        logging.info("Getting CPU time by PID: %s", pid)
    if pid:
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as stat_file:
                parts = stat_file.read().split()
                utime = int(parts[13])  # User time
                stime = int(parts[14])  # System time
                # Convert jiffies to seconds. Assume USER_HZ = 100 for simplicity.
                # fmt: off
                jiffies_per_second = os.sysconf("SC_CLK_TCK")  # pylint: disable=no-member disable=line-too-long # sysconf is actually a function of os, but pylint doesn't know that
                # fmt: on
                if log:
                    logging.info("jiffies_per_second: %s", jiffies_per_second)
                cpu_time = (utime + stime) / jiffies_per_second

            # Calculate the CPU usage in percentage using the number of cores,
            # time delta since last check and CPU time delta
            cores = app_settings.localserver.cpu_cores
            if log:
                logging.info(
                    "last_cpu_check: %s",
                    app_settings.localserver.last_cpu_check,
                )
                logging.info(
                    "last_cpu_time: %s", app_settings.localserver.last_cpu_time
                )
            if (
                app_settings.localserver.last_cpu_check is not None
                and app_settings.localserver.last_cpu_time is not None
            ):
                time_delta = (
                    datetime.now() - app_settings.localserver.last_cpu_check
                ).total_seconds()
                cpu_delta = cpu_time - app_settings.localserver.last_cpu_time
                cpu_usage = (cpu_delta / (time_delta * cores)) * 100
                cpu_usage = round(cpu_usage, 2)
            else:
                cpu_usage = 0

            app_settings.localserver.last_cpu_check = datetime.now()
            app_settings.localserver.last_cpu_time = cpu_time
            result["status"] = "success"
            result["cpu_time"] = cpu_time
            result["cpu_usage"] = cpu_usage
        except IOError as e:
            result["status"] = "error"
            result["value"] = "Error accessing process stats"
            logging.info("Error accessing process stats: %s", e)
    return result


def check_server_running() -> dict:
    """Check if the server is running by PID."""
    log = False
    result = {}
    if not app_settings.localserver.pid:
        identify_process_by_name()

    if (
        not app_settings.localserver.pid
    ):  # If the PID is still not set, the server is not running
        result["status"] = "success"
        result["value"] = False
        result["cpu_time"] = "0"
        result["cpu_usage"] = "0"
        result["ram_usage"] = "0"
        return result

    if app_settings.app_os == "Windows":
        if app_settings.localserver.use_get_counters:
            find_cmd = f'$TargetInstance = "{app_settings.localserver.counters_instance_name}"; $CounterPaths = @("\\Process($TargetInstance)\\% Processor Time","\\Process($TargetInstance)\\Working Set - Private"); Get-Counter -Counter $CounterPaths | ForEach-Object {{ $cpuTime = [Math]::Round($_.CounterSamples[0].CookedValue , 2); $ramUsage = $_.CounterSamples[1].CookedValue; "$cpuTime $ramUsage" }}'  # pylint: disable=line-too-long
        else:
            find_cmd = f'$TargetPID = "{app_settings.localserver.pid}"; Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object {{ $_.IDProcess -eq $TargetPID }} | Select-Object -Property Name, PercentProcessorTime, WorkingSet -First 1 | ForEach-Object {{ $cpuUsage = $_.PercentProcessorTime; $workingSetSize = $_.WorkingSet; "$cpuUsage $workingSetSize" }}'  # pylint: disable=line-too-long

        if log:
            logging.info("CMD: %s", find_cmd)
        try:
            process = subprocess.run(
                ["powershell", f"{find_cmd}"],
                check=True,
                capture_output=True,
                text=True,
                shell=True,
            )
            cmd_output = process.stdout.strip()
            if log:
                logging.info("CMD Output: %s", cmd_output)
            if cmd_output:
                app_settings.localserver.get_counters_succeeded = True
                # Handle CPU Usage
                if app_settings.localserver.is_virtual_machine:
                    cpu_usage = (
                        float(cmd_output.split()[0])
                        / app_settings.localserver.cpu_cores
                    )  # Normalize CPU usage for virtual machines
                else:
                    cpu_usage = float(cmd_output.split()[0])  # CPU usage
                cpu_usage = round(cpu_usage, 2)  # Round to 2 decimal places
                ram = (
                    float(cmd_output.split()[1]) / 1073741824
                )  # Convert to GB
                result["status"] = "success"
                result["value"] = True
                result["cpu_usage"] = str(cpu_usage)
                result["ram_usage"] = str(round(ram, 2))

                if log:
                    logging.info(
                        "Server Monitoring:\nCPU Usage: %s\nRAM Usage: %s",
                        result["cpu_usage"],
                        result["ram_usage"],
                    )
            else:
                result["status"] = "success"
                result["value"] = False
                result["cpu_time"] = "0"
                result["cpu_usage"] = "0"
                result["ram_usage"] = "0"
                app_settings.localserver.running = False
                app_settings.localserver.pid = None
                app_settings.localserver.last_cpu_check = None
                app_settings.localserver.last_cpu_time = None
                if log:
                    logging.info("Server is not running: %s", result)
        except subprocess.CalledProcessError as e:
            # # If Get-Counter fails, switch to WMI and try again
            # if (
            #     app_settings.localserver.use_get_counters
            #     and not app_settings.localserver.get_counters_succeeded
            #     and not app_settings.localserver.installing
            # ):
            #     app_settings.localserver.use_get_counters = False
            #     logging.info(
            #         "Switching to WMI from Get-Counters and trying again..."
            #     )
            #     return check_server_running()

            # Check if the exit status was 1, which means the process was not found
            if e.returncode == 1:
                result["status"] = "success"
                result["value"] = False
                result["cpu_time"] = "0"
                result["cpu_usage"] = "0"
                result["ram_usage"] = "0"
                app_settings.localserver.running = False
                app_settings.localserver.pid = None
                app_settings.localserver.last_cpu_check = None
                app_settings.localserver.last_cpu_time = None
                if log:
                    logging.info("Server is not running: %s", result)
            else:
                result["status"] = "error"
                result["value"] = (
                    "Can't identify server process using Get-Counter or WMI"
                )
                logging.info("Error identifying server process: %s", e)

            return result
    else:
        pid = app_settings.localserver.pid

        if app_settings.localserver.server_process:
            # Check if the process is still running
            if app_settings.localserver.server_process.poll() is not None:
                # Process has terminated
                app_settings.localserver.server_process.wait()
                result["status"] = "success"
                result["value"] = False
                result["cpu_time"] = "0"
                result["cpu_usage"] = "0"
                result["ram_usage"] = "0"
                app_settings.localserver.running = False
                app_settings.localserver.pid = None
                app_settings.localserver.last_cpu_check = None
                app_settings.localserver.last_cpu_time = None
                return result
        if pid:
            cpu_result = get_cpu_time_by_pid(pid)
            if cpu_result["status"] == "error":
                result["status"] = "success"
                result["value"] = False
                result["cpu_time"] = "0"
                result["cpu_usage"] = "0"
                result["ram_usage"] = "0"
                logging.info("Process appears not to be running")
                return result
            else:
                if log:
                    logging.info("CPU Usage: %s", cpu_result)
                result["cpu_time"] = cpu_result["cpu_time"]
                result["cpu_usage"] = cpu_result["cpu_usage"]

            ram_result = get_ram_usage_by_pid(pid)
            if ram_result["status"] == "success":
                if log:
                    logging.info("RAM Usage: %s", ram_result)
                result["ram_usage"] = ram_result["value"]
            result["status"] = "success"
            result["value"] = True
    return result


def terminate_process_by_pid(pid: int):
    """Terminate a process by its PID."""
    if app_settings.app_os == "Windows":
        try:
            terminate_cmd = f'powershell "Stop-Process -Id {pid} -Force"'
            subprocess.run(terminate_cmd, check=True, shell=True)
            info = f"Terminated process with ID {pid}."
            app_settings.localserver.running = False
            logging.info(info)
            return True
        except subprocess.CalledProcessError as e:
            info = f"Failed to terminate process with ID {pid}: {e}"
            logging.error(info)
            return False
    else:
        try:
            # Attempt graceful termination with SIGTERM first
            # subprocess.run(["kill", "-SIGTERM", str(pid)], check=True)
            # logging.info("Sent SIGTERM to terminate process with ID %s", pid)

            # Optionally, wait a bit and check if process needs to be killed forcefully
            # This can be done using `kill -0` to check if process still exists,
            # and `kill -SIGKILL` if it does
            # For simplicity, this example does not include the check and wait logic

            # Uncomment the below lines to forcefully terminate if the process does not stop
            # time.sleep(2)  # Wait for the process to terminate
            subprocess.run(["kill", "-SIGKILL", str(pid)], check=True)
            info = f"Forcibly terminated process with ID {pid} using SIGKILL."
            logging.info(
                "Forcibly terminated process with id %s using SIGKILL", {pid}
            )

            app_settings.localserver.running = False
            return True
        except subprocess.CalledProcessError as e:
            info = f"Failed to terminate process with ID {pid}: {e}"
            logging.error(info)
            return False


def delete_existing_settings():
    """Delete existing settings on the server."""
    result = {}
    try:
        logging.info("Deleting existing settings on the server")
        # Check that file exists
        settings_file = app_settings.localserver.ini_path
        if os.path.isfile(settings_file):
            os.remove(settings_file)
            # Check that file was deleted
            if not os.path.isfile(settings_file):
                result["status"] = "success"
                result["message"] = "Existing settings deleted from the server"
                logging.info("Existing settings deleted from the server")
        else:
            result["status"] = "success"
            result["message"] = "No existing settings found on the server"
            logging.info("No existing settings found on the server")
    except Exception as e:  # pylint: disable=broad-except
        info = f"Error deleting existing settings on the server: {e}"
        logging.error(info)
        result["status"] = "error"
        result["message"] = "Error deleting existing settings on the server"
    return result


def copy_default_settings():
    """Copy default settings to the server."""
    logging.info("Copying default settings to the server")
    result = {}
    default_file = app_settings.localserver.default_ini_path
    logging.info("Default settings file: %s", default_file)
    settings_file = app_settings.localserver.ini_path
    logging.info("Settings file: %s", settings_file)
    # Only proceed if the default settings file exists, otherwise return an error
    if os.path.isfile(default_file):

        # Delete existing settings on the server before copying the default settings
        deleted = delete_existing_settings()
        # If there was an error deleting the existing settings, return the error
        if deleted["status"] == "error":
            return deleted

        # Copy default settings to the server
        try:
            logging.info("Copying default settings to the server")
            shutil.copy(default_file, settings_file)
            if os.path.isfile(settings_file):
                result["status"] = "success"
                result["message"] = "Default settings copied to the server"
                logging.info("Default settings copied to the server")
            else:
                result["status"] = "error"
                result["message"] = (
                    "Error copying default settings to the server"
                )
                logging.info("Error copying default settings to the server")
        except Exception as e:  # pylint: disable=broad-except
            result["status"] = "error"
            result["message"] = "Error copying default settings to the server"
            logging.error(
                "Error copying default settings to the server: %s", e
            )
        return result
    else:
        result["status"] = "error"
        result["message"] = "Default settings file not found"
        return result


def update_palworld_settings_ini(settings_to_change: dict = None):
    """Update the PalWorld settings file."""
    result = {}

    def quote_value_if_needed(value):
        # Check if the value is already properly quoted
        if value.startswith('"') and value.endswith('"'):
            return value  # Return the value as is if it's already quoted

        # Check if the value contains special characters or spaces and needs to be quoted
        if any(char in value for char in " ,()") or " " in value:
            return f'"{value}"'  # Quote the value
        return value  # Return as is if no quoting is needed

    def split_settings_string(settings_string):
        # This regex pattern matches commas that are not inside quotes
        pattern = r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)'
        return re.split(pattern, settings_string)

    logging.info(
        "Updating PalWorld settings file. Settings to change:\n%s",
        settings_to_change,
    )

    public_ip = get_public_ip()
    if not public_ip:
        result["status"] = "error"
        result["message"] = "Error getting public IP address"
        return result
    settings_to_change["PublicIP"] = f'"{public_ip}"'

    if settings_to_change["RCONEnabled"] == "true":
        settings_to_change["RCONEnabled"] = "True"
    elif settings_to_change["RCONEnabled"] == "false":
        settings_to_change["RCONEnabled"] = "False"

    lines: list = []
    lines_read = file_to_lines(app_settings.localserver.ini_path)
    if lines_read["status"] == "error":
        return lines_read
    else:
        lines = lines_read["lines"]

    try:
        line: str
        for i, line in enumerate(lines):
            if line.startswith("OptionSettings="):
                # Extract the settings string
                settings_line: str = line
                settings_string_start = settings_line.find("(") + 1
                settings_string_end = settings_line.rfind(")")

                if settings_string_end > settings_string_start:
                    settings_string = settings_line[
                        settings_string_start:settings_string_end
                    ]
                else:
                    result["status"] = "error"
                    result["message"] = (
                        "Error reading settings file, settings_string_end"
                        + " is less than settings_string_start"
                    )
                    return result

                # create a copy of settings_to_change called settings_changed
                settings_left_to_change = settings_to_change.copy()

                # Break down and sort the settings
                settings = split_settings_string(settings_string)
                modified_settings = []
                for setting in settings:
                    logging.info("Setting: %s", setting)
                    key, _, value = setting.partition("=")
                    key = key.strip()
                    if key in settings_to_change:
                        # Quote the new value if necessary, without escaping quotes
                        new_value = quote_value_if_needed(
                            settings_to_change[key]
                        )
                        setting = f"{key}={new_value}"
                        modified_settings.append(setting)
                        settings_left_to_change.pop(key)
                    else:
                        # Ensure existing values are properly handled
                        modified_settings.append(
                            f"{key}={quote_value_if_needed(value)}"
                        )

                # Add any new settings that were not found in the existing settings
                for key, value in settings_left_to_change.items():
                    modified_settings.append(
                        f"{key}={quote_value_if_needed(value)}"
                    )

                # Rebuild the modified settings string
                modified_settings_string = ",".join(modified_settings)
                modified_settings_line = (
                    f"OptionSettings=({modified_settings_string})\n"
                )

                # Replace the original line with the modified line
                lines[i] = modified_settings_line
        # Write the updated settings back to the file
        with open(
            app_settings.localserver.ini_path, "w", encoding="utf-8"
        ) as file:
            file.writelines(lines)

        result["status"] = "success"
        result["message"] = "Settings updated successfully"
        logging.info("Settings updated successfully")
    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["message"] = "Error writing settings file"
        logging.error("Error writing settings file: %s", e)
    return result


def first_run():
    """Run server after clean install to create initial files."""
    result = {}
    app_settings.localserver.expected_to_be_running = True
    logging.info("Running server for the first time to create initial files.")
    launcher_args = {
        "rcon_port": "25575",
        "port": "8211",
        "public_port": "8211",
        "query_port": "27015",
        "useperfthreads": True,
        "NoAsyncLoadingThread": True,
        "UseMultithreadForDS": True,
        "launch_rcon": False,
        "auto_backup": True,
        "auto_backup_delay": "3600",
        "auto_backup_quantity": "48",
        "publiclobby": False,
        "auto_restart_triggers": True,
        "auto_restart_on_unexpected_shutdown": True,
        "ram_restart_trigger": "0",
        "steam_auth": False,
        "enforce_steam_auth_ip": False,
        "discord_bot_enabled": False,
        "discord_bot_token": "",
        "discord_bot_server_id": "",
        "discord_bot_channel_id": "",
        "discord_bot_admin_role_id": "",
        "discord_bot_rcon_role_id": "",
        "discord_bot_rcon_enabled": False,
        "discord_bot_joins_enabled": False,
        "discord_bot_leaves_enabled": False,
    }
    run_server(launcher_args)
    time.sleep(3)

    terminated = terminate_process_by_pid(app_settings.localserver.pid)
    logging.info("Server termination status: %s", terminated)
    if terminated:
        copied = copy_default_settings()
        app_settings.localserver.running = False
        app_settings.localserver.expected_to_be_running = False
        if copied["status"] == "success":
            app_settings.set_local_server_paths()
            settings_to_change = {  # Used to enable RCON
                "RCONEnabled": "True",
                "AdminPassword": '"admin"',
                "bShowPlayerList": "False",
            }
            rcon_enabled = update_palworld_settings_ini(settings_to_change)
            if rcon_enabled["status"] == "success":
                result["status"] = "success"
                result["message"] = "Server installed successfully"
                return result
            else:
                result["status"] = "error"
                result["message"] = "Error enabling RCON on the server"
                return result
        else:
            result["status"] = "error"
            result["message"] = "Error copying default settings to the server"
            return result
    else:
        result["status"] = "error"
        result["message"] = "Error terminating server"
        return result


def install_server() -> dict:
    """Install the server."""
    result = {}
    if not app_settings.localserver.steamcmd_installed:
        steamcmd_result = install_steamcmd()
    else:
        steamcmd_result = {
            "status": "success",
            "message": "SteamCMD already installed",
        }
    palserver_result = install_palserver()
    saved_data_result = check_palworld_install()
    result["steamcmd"] = steamcmd_result
    result["palserver"] = palserver_result
    result["saved_data"] = saved_data_result
    if (
        steamcmd_result["status"] == "success"
        and palserver_result["status"] == "success"
    ):
        result["status"] = "success"
        result["message"] = "Server installed successfully"
    if saved_data_result["value"] is False:
        first_run_result = first_run()
        result["first_run"] = first_run_result
        if first_run_result["status"] == "success":
            result["status"] = "success"
            result["message"] = "Server installed successfully"
    return result


def backup_server(query: dict) -> dict:
    """Backup the server data."""
    logging.info("Backing up server data with query: %s", query)
    result = {}
    if "backup_type" in query:
        backup_type = query["backup_type"]
    if "backup_count" in query:
        backup_count = query["backup_count"]
    logging.info(
        "Backing up server data from %s to %s",
        app_settings.localserver.data_path,
        app_settings.localserver.backup_path,
    )
    backup_path = app_settings.localserver.backup_path
    data_path = app_settings.localserver.data_path
    try:
        # Check if the backup path exists, if not create it
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)
            logging.info("Created backup path: %s", backup_path)
        # Create a timestamp for the backup
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        # Create the backup folder
        if backup_type == "manual":
            backup_folder = os.path.join(backup_path, f"{timestamp}", "Saved")
        elif backup_type == "launch":
            backup_folder = os.path.join(
                backup_path, f"{timestamp}-LaunchBackup", "Saved"
            )
        elif backup_type == "firstrun":
            backup_folder = os.path.join(
                backup_path, f"{timestamp}-FirstRunBackup", "Saved"
            )
        else:
            backup_folder = os.path.join(
                backup_path, f"{timestamp}-AutoBackup", "Saved"
            )
        # Copy the data to the backup folder
        shutil.copytree(data_path, backup_folder)
        # Verify that the data was copied by comparing the contents of the data and backup folders
        data_contents = os.listdir(data_path)
        backup_contents = os.listdir(backup_folder)
        if data_contents == backup_contents:
            result["status"] = "success"
            result["message"] = "Server data backed up successfully"
            logging.info("Copied data to backup folder: %s", backup_folder)
        else:
            # If the contents of the data and backup folders do not match, delete the backup folder
            if os.path.exists(backup_folder):
                shutil.rmtree(backup_folder)
            result["status"] = "error"
            result["message"] = "Error backing up server data"
            logging.error("Error backing up server data")

        # If the backup count is greater than 0, delete old backups
        if int(backup_count) > 0:
            folders_to_prune = []
            # If the backup count is greater than 0,
            # delete old backups that have AutoBackup in the name
            backup_folders = [
                f
                for f in os.listdir(backup_path)
                if os.path.isdir(os.path.join(backup_path, f))
            ]
            # remove backup folders that do not have AutoBackup in the name

            for folder in backup_folders:
                if folder.find("AutoBackup") != -1:
                    folders_to_prune.append(folder)

            folders_to_prune.sort(reverse=False)

            # remove old backups
            if len(folders_to_prune) > int(backup_count):
                # Remove len(folders_to_prune) - int(backup_count) old backups
                for i in range(len(folders_to_prune) - int(backup_count)):
                    folder_to_prune = os.path.join(
                        backup_path, folders_to_prune[i]
                    )
                    shutil.rmtree(folder_to_prune)
                    logging.info("Pruned Old Backup: %s", folder_to_prune)

    except Exception as e:  # pylint: disable=broad-except
        result["status"] = "error"
        result["message"] = "Exception while backing up server data"
        logging.error("Exception while backing up server data: %s", e)
    return result


def generate_world_option_save(data: dict) -> dict:
    """Generate WorldOption.sav and return it as a file download."""
    # Generate WorldOption.sav.json and convert it to WorldOption.sav
    result = {}
    properties_data = {
        "Settings": {
            "struct_type": "PalOptionWorldSettings",
            "struct_id": "00000000-0000-0000-0000-000000000000",
            "id": None,
            "value": {},
            "type": "StructProperty",
        }
    }

    for (
        key,
        default_value,
    ) in app_settings.palworldsettings_defaults.default_values.items():
        submitted_value = data.get(key, default_value)
        if str(submitted_value) != str(default_value):
            if submitted_value.lower() in ["true", "false"]:
                value = True if submitted_value.lower() == "true" else False
                _type = "BoolProperty"
            elif submitted_value.replace(".", "", 1).isdigit():
                value = (
                    float(submitted_value)
                    if "." in submitted_value
                    else int(submitted_value)
                )
                _type = (
                    "FloatProperty"
                    if "." in submitted_value
                    else "IntProperty"
                )
            else:
                # Remove single and double quotes from the submitted value
                remove = ["'", '"']
                for char in remove:
                    submitted_value = submitted_value.replace(char, "")
                value = submitted_value
                _type = "StrProperty"

            properties_data["Settings"]["value"][key] = {
                "id": None,
                "value": value,
                "type": _type,
            }

    json_data = {
        "header": app_settings.palworldsettings_defaults.worldoptionsav_json_data_header,
        "properties": {
            "Version": {"id": None, "value": 100, "type": "IntProperty"},
            "OptionWorldData": {
                "struct_type": "PalOptionWorldSaveData",
                "struct_id": "00000000-0000-0000-0000-000000000000",
                "id": None,
                "value": properties_data,
                "type": "StructProperty",
            },
        },
        "trailer": "AAAAAA==",
    }

    # Save the JSON data to a file named 'WorldOption.sav.json'
    with open(
        os.path.join("./", "WorldOption.sav.json"), "w", encoding="utf-8"
    ) as json_file:
        json.dump(json_data, json_file, indent=2)

    # Check if WorldOption.sav exists and delete it
    if os.path.exists("WorldOption.sav"):
        os.remove("WorldOption.sav")

    # Run convert.py with the saved file as an argument
    # subprocess.run(["python3", "convert.py", "WorldOption.sav.json"])
    convert_json_to_sav("WorldOption.sav.json", "WorldOption.sav")

    # Delete the file from the filesystem
    os.remove("WorldOption.sav.json")

    # move WoldOption.sav to app_settings.localserver.sav_path directory
    # replace the existing file if it exists
    # check if app_settings.localserver.sav_path exists
    if not os.path.exists(app_settings.localserver.sav_path):
        os.makedirs(app_settings.localserver.sav_path)
    target_file = os.path.join(
        app_settings.localserver.sav_path, "WorldOption.sav"
    )
    if os.path.exists(target_file):
        os.remove(target_file)
    shutil.copy("WorldOption.sav", target_file)

    # Verify that the file was copied successfully by checking that
    # the original and copied files are identical
    if filecmp.cmp("WorldOption.sav", target_file):
        result["success"] = True
        result["message"] = "WorldOption.sav generated successfully"
    else:
        result["success"] = False
        result["message"] = "Error generating WorldOption.sav"

    # Remove original WorldOption.sav file
    os.remove("WorldOption.sav")

    return result


def uninstall_server():
    """Uninstall Palworld Dedicated Server and SteamCMD"""
    result = {}
    if app_settings.app_os == "Windows":
        try:
            # Uninstall Palworld Dedicated Server
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(
                [
                    "powershell",
                    "Remove-Item",
                    "-Path",
                    os.path.dirname(app_settings.localserver.steamcmd_path),
                    "-Recurse",
                ],
                capture_output=True,
                check=True,
                startupinfo=startupinfo,
                text=True,
            )

            # Verify that the directory was removed
            if not os.path.exists(
                os.path.dirname(app_settings.localserver.steamcmd_path)
            ):
                result["status"] = "success"
                result["message"] = (
                    "Palworld Dedicated Server uninstalled successfully"
                )
            else:
                result["status"] = "error"
                result["message"] = (
                    "Error uninstalling Palworld Dedicated Server"
                )
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error uninstalling Palworld Dedicated Server"
            logging.info("Error uninstalling Palworld Dedicated Server: %s", e)
    else:
        home_dir = os.environ["HOME"]
        try:
            # Uninstall Palworld Dedicated Server
            subprocess.run(
                [
                    "sudo",
                    "apt-get",
                    "remove",
                    "steamcmd",
                    "-y",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "rm",
                    "-rf",
                    f"{home_dir}/.local/share/Steam",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "rm",
                    "-rf",
                    f"{home_dir}/.steam",
                ],
                check=True,
            )

            # check that /usr/games/steamcmd does not exist
            if not os.path.exists("/usr/games/steamcmd"):
                steamcmd_uninstalled = True

            # Verify that directories were removed
            if not os.path.exists(
                f"{home_dir}/.local/share/Steam"
            ) and not os.path.exists(f"{home_dir}/.steam"):
                directories_removed = True

            if steamcmd_uninstalled and directories_removed:
                result["status"] = "success"
                result["message"] = (
                    "Palworld Dedicated Server uninstalled successfully"
                )
            else:
                result["status"] = "error"
                result["message"] = (
                    "Error uninstalling Palworld Dedicated Server"
                )
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = "Error uninstalling Palworld Dedicated Server"
            logging.info("Error uninstalling Palworld Dedicated Server: %s", e)

    return result


def install_ue4ss() -> dict:
    """Install Unreal Engine 4/5 Scripting System."""
    log = True
    result = {}
    ue4ss_url = "https://api.github.com/repos/UE4SS-RE/RE-UE4SS"
    uer22_latest_url = f"{ue4ss_url}/releases/latest"
    ue4ss_friendly_url = "https://github.com/UE4SS-RE/RE-UE4SS"
    # Use requests to check github API for latest release for https://github.com/UE4SS-RE/RE-UE4SS
    try:
        response = requests.get(
            uer22_latest_url,
            timeout=5,
        )
        response.raise_for_status()
        release = response.json()

        result["release"] = json.dumps(release, indent=2)

        version = release["tag_name"]
        if log:
            logging.info("Latest release: %s", version)
        result["version"] = version

        # In release["assets"], find the asset with the name "UE4SS_{version}.zip"
        asset = next(
            (
                asset
                for asset in release["assets"]
                if asset["name"] == f"UE4SS_{version}.zip"
            ),
            None,
        )

        if asset is None:
            raise requests.exceptions.RequestException(
                f"UE4SS asset matching version {version} not found in the release assets"
            )
        result["asset"] = json.dumps(asset, indent=2)

        download_url = asset["browser_download_url"]
        if download_url is None:
            raise requests.exceptions.RequestException(
                "UE4SS download URL not found in the release assets"
            )
        if log:
            logging.info("Download URL: %s", download_url)
        result["download_url"] = download_url

        # Download the asset using download_file function
        download_result = download_file(
            download_url, "UE4SS.zip", app_settings.exe_path
        )
        result["download_result"] = download_result

        if not download_result["success"]:
            result["success"] = False
            result["message"] = download_result["message"]
            return result

        # Extract the downloaded zip file to app_settings.localserver.binaries_path
        extraction_result = extract_file(
            app_settings.exe_path,
            "UE4SS.zip",
            app_settings.localserver.binaries_path,
        )
        result["extraction_result"] = extraction_result
        if not extraction_result["success"]:
            result["success"] = False
            result["message"] = extraction_result["message"]
            return result

        os.remove(os.path.join(app_settings.exe_path, "UE4SS.zip"))

        result = {
            "status": "success",
            "message": f'UE4SS {version} installed successfully. For more info, visit [LINK url="{ue4ss_friendly_url}"" name="UE4SS Github"]',
        }

    except requests.exceptions.RequestException as e:
        result["success"] = False
        result["message"] = f"Error installing UE4SS: {e}"

    return result


def install_palguard(data: dict = None) -> dict:
    """Install PalGuard."""

    palguard_nexusmods = "https://www.nexusmods.com/palworld/mods/451"
    palguard_discord = "https://discord.gg/jcvKpkUmXS"

    result = {}

    if data is None:
        result["success"] = False
        result["message"] = "No data provided"
        return result

    if "version" not in data:
        result["success"] = False
        result["message"] = "No version provided"
        return result

    if "Windows" not in data:
        result["success"] = False
        result["message"] = "No Windows download URL provided"
        return result

    if "ProtonWine" not in data:
        result["success"] = False
        result["message"] = "No ProtonWine download URL provided"
        return result

    version = data["version"]
    windows_url = data["Windows"]
    protonwine_url = data["ProtonWine"]

    if app_settings.app_os == "Windows":
        download_url = windows_url
    elif app_settings.app_os == "Wine":
        download_url = protonwine_url
    else:
        result["success"] = False
        result["message"] = "Unsupported OS"
        return result

    download_result = download_file(
        download_url, f"PalGuard_{version}.zip", app_settings.exe_path
    )
    if not download_result["success"]:
        result["success"] = False
        result["message"] = download_result["message"]
        return result

    extraction_result = extract_file(
        app_settings.exe_path,
        f"PalGuard_{version}.zip",
        app_settings.localserver.binaries_path,
    )
    if not extraction_result["success"]:
        result["success"] = False
        result["message"] = extraction_result["message"]
        return result

    os.remove(os.path.join(app_settings.exe_path, f"PalGuard_{version}.zip"))

    result["success"] = True
    result["message"] = (
        f'PalGuard {version} installed successfully. For more info, visit [LINK url="{palguard_nexusmods}" name="PalGuard NexusMods"] or [LINK url="{palguard_discord}" name="PalGuard Discord"]'
    )

    return result
