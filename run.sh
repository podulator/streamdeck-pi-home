#!/usr/bin/bash
LOGFILE="/tmp/streamdeck.log"
MAIN="streamdeck_launcher.py"

logger() {
    echo ${1}
    echo ${1} >> ${LOGFILE}
}

echo "Starting our launcher" > ${LOGFILE}

logger "Activating our venv..."
source venv/bin/activate
result=$?
if [[ ${result} -ne 0 ]]; then
    logger "Couldn't activate our environment"
    logger "Return code was : ${result}"
    exit ${result}
fi

while : ; do
    if ! /bin/pgrep -f "${MAIN}" &> /dev/null; then
        logger "Launching the app..." 
        python -u ./${MAIN} "$@" 2>> ${LOGFILE}
        exit_code=$?
        logger "Run exited with code : ${exit_code}"
        if [[ ${exit_code} -ne 134 ]]; then
            break
        fi
    fi
    sleep 5
done

logger "Launcher exited"
