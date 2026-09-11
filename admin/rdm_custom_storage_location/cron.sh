*/30 * * * * curl "http://localhost:8001/custom_storage_location/external_acc_update/$(cd /code && python3 manage.py generate_signed_cron_token)/" | jq -c .
