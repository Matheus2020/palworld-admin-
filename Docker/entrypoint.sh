#!/bin/bash

# Ensure the application directory exists
PALWORLD_DIR="/home/lukium/palworld-admin"
mkdir -p "$PALWORLD_DIR"

# Set Wine environment variables
export WINEPREFIX="/home/lukium/.wine"
export WINEDEBUG=-all

# GitHub API URL for the latest release
API_URL="https://api.github.com/repos/Lukium/palworld-admin/releases/latest"

# Fetch the latest release data from GitHub API
LATEST_RELEASE=$(curl -s $API_URL)

# Extract the tag_name for version (remove the leading 'v')
LATEST_VERSION=$(echo "$LATEST_RELEASE" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')

# Path for the version file
VERSION_FILE="$PALWORLD_DIR/version"

# Check if the version file exists and read the version; if not found, set to 0 for comparison
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE")
else
    CURRENT_VERSION="0"
fi

# Compare versions
VERSION_COMPARISON=$(printf "%s\n%s" "$LATEST_VERSION" "$CURRENT_VERSION" | sort -V | head -n 1)

# If the latest version is newer, download and update
if [ "$VERSION_COMPARISON" != "$LATEST_VERSION" ]; then
    echo "Updating to latest version: $LATEST_VERSION"

    # Extract the download URL for the palworld-admin-linux file
    DOWNLOAD_URL=$(echo "$LATEST_RELEASE" | grep '"browser_download_url":.*palworld-admin-linux"' | sed -E 's/.*"([^"]+)".*/\1/')

    # Download the palworld-admin-linux file from the latest release
    curl -L "$DOWNLOAD_URL" -o "$PALWORLD_DIR/palworld-admin-linux"

    # Make the binary executable
    chmod +x "$PALWORLD_DIR/palworld-admin-linux"

    # Store the version number
    echo "$LATEST_VERSION" > "$VERSION_FILE"
else
    echo "Already at the latest version: $CURRENT_VERSION"
fi

# Echo the MANAGEMENT_PASSWORD and MANAGEMENT_PORT before running the application
echo "Launching Palworld Admin with MANAGEMENT_PASSWORD: $MANAGEMENT_PASSWORD and MANAGEMENT_PORT: $MANAGEMENT_PORT"

# Run the application
"$PALWORLD_DIR/palworld-admin-linux" -mdb
exec "$PALWORLD_DIR/palworld-admin-linux" -ls -r -mp "$MANAGEMENT_PASSWORD" -p "$MANAGEMENT_PORT"