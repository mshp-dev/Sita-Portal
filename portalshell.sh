#!/usr/bin/bash

cd /opt/mftusers
source venv/bin/activate
python manage.py shell
#<<EOF
#from core.models import *
#from mftusers.utils import *
#EOF
