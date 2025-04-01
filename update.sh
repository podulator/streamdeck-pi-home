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
	# silent upgrade of pip
	source ./venv/bin/activate && pip install -Ur ./requirements.txt 1>/dev/null 2>&1
	git pull | tail -n 1
fi
