#!/bin/bash

# Apply database migrations
python manage.py migrate

# Check if initial setup needs to be run
# This can be done by checking for a file that is created after the initial setup

SETUP_DONE="/app/setup_done.txt"
if [ ! -f "$SETUP_DONE" ]; then
    echo "Running initial setup..."
    python manage.py create_notification_template
    python manage.py create_roles
    python manage.py create_courses

    # Mark initial setup as done
    touch $SETUP_DONE
fi

# Start the Django server
python manage.py runserver 0.0.0.0:8000
