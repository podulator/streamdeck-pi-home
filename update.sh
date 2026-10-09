#!/usr/bin/bash

added=$(git status -s -u normal | wc -l)
modified=$(git ls-files -m | wc -l)
if [ ${modified} -ne 0 ]; then
	echo "Local modifications : "
	git ls-files -m | head -n 2
	exit 1
elif [ ${added} -ne 0 ]; then
	echo "Locally added files : "
	git status -s | head -n 2
	exit 1
else
	# pull first, so a change to requirements.txt / constraints.txt is installed in the same run
	git pull | tail -n 1
	# exact versions from constraints.txt; packages only move when that file is changed in git
	source ./venv/bin/activate
	if ! pip install -q -r ./requirements.txt -c ./constraints.txt > /tmp/streamdeck-pip.log 2>&1; then
		echo "pip install failed, see /tmp/streamdeck-pip.log"
		tail -n 5 /tmp/streamdeck-pip.log
		exit 1
	fi
fi
