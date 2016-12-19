#!/bin/bash

cd "$( dirname "${BASH_SOURCE[0]}")"
cd ..

if [ $# -lt 1 ]; then
    exit 1
fi

YEAR=$1

source ../env/bin/activate
python -c "from uspto_fast.models import *; print new_session().query(Patent).filter_by(apply_year=${YEAR}).count()"