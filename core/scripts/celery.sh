#!/bin/bash
celery -A exchange worker --autoscale=1,4 --loglevel=info -Q celery,accounts,market,admin,cache,notif,margin,staking,credit,socialtrade,files,abc,xchange,webengage,direct_debi,telegram,telegram_admin,liquidator,liquidator_internal_orders
