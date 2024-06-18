#!/usr/bin/env bash

# We have an initial signal number registration
set -e

if [ ! -f /signald-sock/setup_completed ]; then
    # raise an error if the setup has not been completed
    echo "Setup has not been completed. Please run the setup script (see README.md)."
    # assert that the /signald-sock directory exists
    if [ ! -d /signald-sock ]; then
        echo "The /signald-sock directory does not exist. Please attach it properly and run the setup script."
        exit 1
    fi
    /signald/build/install/signald/bin/signald --socket=/signald-sock/signald.sock &
    sleep 500
else
    /signald/build/install/signald/bin/signald --socket=/signald-sock/signald.sock
fi
exec "$@"
