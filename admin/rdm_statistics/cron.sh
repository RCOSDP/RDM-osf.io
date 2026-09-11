0 2 * * 1 curl "http://localhost:8001/statistics/gather/$(cd /code && python3 manage.py generate_signed_cron_token)/" | jq -c .
