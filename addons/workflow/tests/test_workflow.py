import os
import json
import subprocess

curr_path = os.path.normpath(os.path.dirname(__file__))
json_path = os.path.abspath(os.path.join(curr_path, os.pardir))
file_path = os.path.join(json_path, 'settings', 'workflow_connection.json')

with open(file_path, 'r') as json_file:
    json_load = json.load(json_file)

name = json_load['engine1']['name']
url = json_load['engine1']['url']
account = json_load['engine1']['account']
password = json_load['engine1']['password']

target = f'http://{account}:{password}@{url}/process-api/repository/process-definitions'

curl_command = [
    'curl',
    '-X', 'GET',
    target
]

result = subprocess.run(
    curl_command,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True
)

print('response code:', result.returncode)
print('response body:', result.stdout)