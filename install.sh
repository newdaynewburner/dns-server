#!/bin/sh

APP_NAME="dnsserverd"
SOURCE_DIR="/usr/lib/rouge-access-point/components/${APP_NAME}"
CONFIG_DIR="/etc/rouge-access-point/components/${APP_NAME}/config"
RSC_DIR="/etc/rouge-access-point/components/${APP_NAME}/rsc"
SYSTEMD_UNIT_TARGET="/etc/systemd/system/${APP_NAME}.service"
SECURITY_POLICY_TARGET="/usr/share/dbus-1/system.d/org.dnsserverd.DNSServer.conf"
BIN_TARGET="/usr/bin/${APP_NAME}"

# Make sure running as root
if [[ "$EUID" -ne 0 ]]; then
	echo "This script must be ran as root! Quitting!"
	exit 1
fi

# Create necessary directories
mkdir -p "${SOURCE_DIR}"
mkdir -p "${CONFIG_DIR}"
mkdir -p "${RSC_DIR}"

# Move script to source directory
echo "Installing application files..."
cp -r dnsserverd.py lib/ "${SOURCE_DIR}/"

# Create the launcher
echo "Creating launcher script..."
cat > "${BIN_TARGET}" <<EOF
#!/bin/sh
exec /usr/bin/env python3 ${SOURCE_DIR}/dnsserverd.py "\$@"
EOF
chmod +x "${BIN_TARGET}"

# Move the configuration file
echo "Copying configuration file..."
cp config/dnsserverd.ini "${CONFIG_DIR}"

# Set up the DBus interface
echo "Copying DBus interface definition and security policy..."
cp rsc/dbus-interface.xml "${RSC_DIR}"
cp rsc/security-policy.conf "${SECURITY_POLICY_TARGET}"

# Set up the systemd unit file
echo "Copying systemd unit..."
cp rsc/systemd-unit.service "${SYSTEMD_UNIT_TARGET}"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

echo "Installation complete!"

