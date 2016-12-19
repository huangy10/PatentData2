#!/bin/bash

cd "$( dirname "${BASH_SOURCE[0]}")"
cd ..

BASE_DIR=$(pwd)
LOG_DIR=${BASE_DIR}/uspto/logs
rm ${LOG_DIR}/*.log
if [ -d ${BASE_DIR}/nohup.out ]; then
    rm ${BASE_DIR}/nohup.out
fi

echo "Done!"