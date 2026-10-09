#!/usr/bin/bash

python=$(which python3)
pyenv=$(which pyenv)
pyver=$( ${python} --version )

# WE NEED TO CHECK IF THE PYTHON VERSION CONTAINS 3.11 exactly
if [[ ${pyver} == *"Python 3.11"* ]]; then
	echo "We have python 3.11"
else
	echo "We need python 3.11"
	echo "current version is : ${pyver}"
	# if we have pyenv installed, we can try to install 3.11
	if [ -z "${pyenv}" ]; then
		echo "You need to install pyenv"
		# https://www.dedicatedcore.com/blog/install-pyenv-ubuntu/
		exit 2
	fi
	if ${pyenv} install -s 3.11; then
		echo "Installed python 3.11"
		${pyenv} local 3.11
		# update our ref to the pyenv version
		python=$(which python3)
		${python} --version
	else
		echo "Failed to install python 3.11"
		exit 3
	fi
fi


# we assume you have installed the platform equivalent of the following deps
# and that you are using pulseaudioon something like debian bookworm
# sudo apt update && sudo apt -y upgrade
# sudo apt -y install python3-dev python3-setuptools \
#	 libtiff5-dev libjpeg-dev libopenjp2-7-dev zlib1g-dev \
#    libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk \
#    libharfbuzz-dev libfribidi-dev libxcb1-dev \
#    libhidapi-libusb0 python3.11-venv vlc sqlite3 pulseaudio-module-bluetooth

# grab the code
# git clone https://github.com/podulator/streamdeck-pi-home.git

udev_file="/etc/udev/rules.d/70-streamdeck.rules"
if [ ! -f ${udev_file} ]; then
	echo "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"0fd9\", TAG+=\"uaccess\", GROUP=\"plugdev\"" | sudo tee ${udev_file} > /dev/null
	sudo udevadm trigger

	in_group=$(id -Gn | tr ' ' '\n' | grep "plugdev" | wc -l)
	if [ ${in_group} -eq 0 ]; then
		echo "You need to add yourself to the plugdev group"
	fi
fi

if [ ! -d "/etc/systemd/system/getty@.service.d" ]; then
	echo "Enabling autologin for pipewire sessions etc"
	# https://github.com/RPi-Distro/raspi-config/blob/master/raspi-config#L1411
	# auto login ourselves to get ready for pipewire needing a session in future
	sudo systemctl --quiet set-default multi-user.target
	sudo mkdir -p /etc/systemd/system/getty@.service.d
	echo "[Service]" | sudo tee /etc/systemd/system/getty@.service.d/override.conf > /dev/null
	echo "ExecStart=" | sudo tee -a /etc/systemd/system/getty@.service.d/override.conf > /dev/null
	echo "ExecStart=-/sbin/agetty --noclear --autologin ${USER} %I ${TERM}" | sudo tee -a /etc/systemd/system/getty@.service.d/override.conf > /dev/null
fi

# the service file is regenerated on every run, so fixes here reach machines that already have one
service_file="/etc/systemd/system/streamdeck.service"
user_id=$(id -u)
cwd=$(pwd)

after="network.target sound.target bluetooth.target"
wants="bluetooth.target"
if [ -e /dev/ttyNFC ]; then
	echo "NFC reader found at /dev/ttyNFC, adding it to the service dependencies"
	after="${after} dev-ttyNFC.device"
	wants="${wants} dev-ttyNFC.device"
else
	echo "No NFC device detected at /dev/ttyNFC, skipping rules"
fi

service_tmp=$(mktemp)
cat > "${service_tmp}" <<SERVICE
[Unit]
Description=Streamdeck Pi Home
After=${after}
Wants=${wants}

[Service]
Type=simple
User=${USER}
WorkingDirectory=${cwd}

Environment=DISPLAY=:0
Environment=XDG_SESSION_TYPE=tty
Environment=HOME=${HOME}
Environment=LANG=en_GB.UTF-8
Environment=XDG_SESSION_CLASS=user
Environment=TERM=xterm-256color
Environment=XDG_SESSION_ID=4
Environment=XDG_RUNTIME_DIR=/run/user/${user_id}
Environment=PULSE_RUNTIME_PATH=/run/user/${user_id}/pulse
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${user_id}/bus
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/games:/usr/games

ExecStartPre=/bin/sleep 5
ExecStart=${cwd}/run.sh config.json

[Install]
WantedBy=multi-user.target
SERVICE

if [ -f "${service_file}" ] && cmp -s "${service_tmp}" "${service_file}"; then
	echo "StreamDeck service file is up to date"
else
	if [ -f "${service_file}" ]; then
		sudo cp "${service_file}" "${service_file}.bak"
		echo "Updating StreamDeck service file (previous version saved as ${service_file}.bak)"
	else
		echo "Installing streamdeck service"
	fi
	sudo install -m 644 "${service_tmp}" "${service_file}"
	sudo systemctl daemon-reload
	sudo systemctl enable streamdeck
	echo "StreamDeck service file written to : ${service_file}"
fi
rm -f "${service_tmp}"

if [ ! -d venv ]; then
	echo "Creating virtual environment"
	${python} -m venv venv
	source ./venv/bin/activate
	echo "Installing dependencies"
	pip install -U wheel pip 2>/dev/null
	pip install -r requirements.txt
fi

printf "Setup finished\nrun: sudo systemctl restart streamdeck\n"
