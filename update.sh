#!/usr/bin/bash

modified=$(git status -s | wc -l)
if [ ${modified} -ne 0 ]; then
	echo "Resolve local modifications"
	git status -s | head -n 2
	exit 1
else
	# silent upgrade of pip
	pip install -Ur ./requirements.txt 1>/dev/null 2>&1
	git pull | tail -n 1
fi
