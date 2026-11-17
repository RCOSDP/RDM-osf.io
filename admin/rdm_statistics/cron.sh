0 2 * * 1 TOKEN=$(cd /code && python3 manage.py generate_signed_cron_token | tail -n1) && [ -n "$TOKEN" ] && curl "http://localhost:8001/statistics/gather/$TOKEN/" | jq -c .
