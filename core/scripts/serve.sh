#!/bin/bash
./manage.py update_email_templates
uwsgi --ini uwsgi/testnet.ini
