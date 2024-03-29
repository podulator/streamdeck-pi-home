#!/usr/bin/bash

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

if [[ ! -d venv ]]; then
	echo "Creating virtual environment"
	python -m venv venv
	source ./venv/bin/activate
	echo "Installing dependencies"
	pip install -U wheel pip 2>/dev/null
	pip install -r requirements.txt
fi

echo "Setup finished"
