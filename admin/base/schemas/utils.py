# -*- coding: utf-8 -*-
import json
import jsonschema
import os

here = os.path.split(os.path.abspath(__file__))[0]


def from_json(file_name):
    with open(os.path.join(here, file_name)) as f:
        return json.load(f)


def validate_json_schema(value, json_schema_name):
    """ Validate JSON data with JSON schema """
    # Load JSON schema file
    json_schema = from_json(json_schema_name)
    # Validate data with the JSON schema
    jsonschema.validate(value, json_schema)


def validate_config_schema(value, json_schema_name):
    """ Validate the config JSON data with config JSON schema and additional logic"""
    # Validate data with the JSON schema
    validate_json_schema(value, json_schema_name)
    # Additional validation for config JSON file
    function_name_list = []
    api_group_list = []
    for json_key, json_value in value.items():
        function_name = json_value.get('function_name')
        api_group = json_value.get('api_group', [])
        function_name_list.append(function_name)
        api_group_list.extend([(item.get('api'), item.get('method'),) for item in api_group])

    # Check if 'function_name' is unique
    is_function_name_list_unique = len(function_name_list) == len(set(function_name_list))
    if not is_function_name_list_unique:
        # If 'function_name' is not unique, raise validation error
        raise jsonschema.ValidationError('Config data is invalid: there are non-unique function_name')

    # Check if 'api_group' is unique
    is_api_group_list_unique = len(api_group_list) == len(set(api_group_list))
    if not is_api_group_list_unique:
        # If 'api_group' is not unique, raise validation error
        raise jsonschema.ValidationError('Config data is invalid: there are non-unique api_group')
