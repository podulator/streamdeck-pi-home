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
	if [ -z ${pyenv} ]; then
		echo "You need to install pyenv"
		# https://www.dedicatedcore.com/blog/install-pyenv-ubuntu/
		exit 2
	fi
	success=$( ${pyenv} install -s 3.11 )
	if [[ ${success} -eq 0 ]]; then
		echo "Installed python 3.11"
		${pyenv} local 3.11
		# update our ref to the pyenv version
		python=$(which python3)
		echo python --version
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

if [ ! -d "/etc/systemd/system/streamdeck.service" ]; then
	echo "Installing streamdeck service"
	service_file="/etc/systemd/system/streamdeck.service"
	user_id=$(id -u ${USER})
	group_id=$(id -g ${USER})
	cwd=$(cwd)

	echo "[Unit]" | sudo tee -a ${service_file} > /dev/null
	echo "Description=Streamdeck Pi Home" | sudo tee -a ${service_file} > /dev/null

	if [ -d /dev/ttyNFC ]; then
		echo "Installing NFC reader support"
		echo "After=network.target sound.target dev-ttyNFC.device" | sudo tee -a ${service_file} > /dev/null
		echo "Wants=dev-ttyNFC.device" | sudo tee -a ${service_file} > /dev/null
	else
		echo "No NFC device detected at /dev/ttyNFC, skipping rules"
	fi
	echo "" | sudo tee -a ${service_file} > /dev/null

	echo "[Service]" | sudo tee ${service_file} > /dev/null
	echo "Type=simple" | sudo tee -a ${service_file} > /dev/null
	echo "User=${USER}" | sudo tee -a ${service_file} > /dev/null
	echo "WorkingDirectory=$(cwd)" | sudo tee -a ${service_file} > /dev/null
	echo "" | sudo tee -a ${service_file} > /dev/null

	echo "Environment=DISPLAY=:0" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=XDG_SESSION_TYPE=tty" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=HOME=/home${USER}" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=LANG=en_GB.UTF-8" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=XDG_SESSION_CLASS=user" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=TERM=xterm-256color" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=XDG_SESSION_ID=4" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=XDG_RUNTIME_DIR=/run/user/${user_id}" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=PULSE_RUNTIME_PATH=/run/user/${user_id}/pulse" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${user_id}/bus" | sudo tee -a ${service_file} > /dev/null
	echo "Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/games:/usr/games" | sudo tee -a ${service_file} > /dev/null

	echo "" | sudo tee -a ${service_file} > /dev/null
	echo "ExecStartPre=/bin/sleep 5" | sudo tee -a ${service_file} > /dev/null
	echo "ExecStart=/home/mat/code/streamdeck-pi-home/run.sh config.json" | sudo tee -a ${service_file} > /dev/null

	sudo chmod 644 /etc/systemd/system/streamdeck.service
	sudo systemctl enable streamdeck

	echo "StreamDeck service file created at : ${service_file}"
fi

if [ ! -d venv ]; then
	echo "Creating virtual environment"
	python -m venv venv
	source ./venv/bin/activate
	echo "Installing dependencies"
	pip install -U wheel pip 2>/dev/null
	pip install -r requirements.txt
fi

echo "Setup finished\nrun: sudo systemctl restart steamdeck-service"
