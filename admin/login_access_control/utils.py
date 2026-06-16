from osf.models import Institution


def validate_integer(value, name):
    """ Check if value is an integer """
    if not value:
        return f'{name} is required.'
    if not isinstance(value, int):
        return f'{name} is invalid.'
    return None


def validate_boolean(value, name):
    """ Check if value is an integer """
    if value is None:
        return f'{name} is required.'
    if not isinstance(value, bool):
        return f'{name} is invalid.'
    return None


def validate_institution_id(institution_id):
    """ Check if value is a ID for existing institution """
    integer_error_message = validate_integer(institution_id, 'institution_id')
    if integer_error_message is not None:
        return integer_error_message
    if not Institution.objects.filter(id=institution_id, is_deleted=False).exists():
        return 'institution_id is invalid.'
    return None


def validate_logic_condition(logic_condition):
    """Validate logic condition expression

    :param str logic_condition: logic condition
    :return bool: logic condition is valid or not
    """
    if not logic_condition:
        # If logic condition is None or empty, return True
        return True

    if not isinstance(logic_condition, str) or has_invalid_character(logic_condition):
        # If logic condition is not a string or has at least one invalid character, return False
        return False

    # Convert operator characters into their respective readable counterpart
    expression = logic_condition. \
        replace('&&', ' and '). \
        replace('||', ' or '). \
        replace('!', ' not ')

    # If converted expression still have & or | then return False
    if expression.find('&') >= 0 or expression.find('|') >= 0:
        return False

    try:
        # Try to evaluate expression
        if not (type(eval(expression)) == int or type(eval(expression)) == bool):
            # If expression is invalid then return False
            return False
    except (SyntaxError, NameError):
        # Fail to evaluate expression, return False
        return False

    # The expression is valid, return True
    return True


def has_invalid_character(expression):
    """ Check if expression has at least one invalid character """
    valid_characters = [' ', '!', '(', ')', '|', '&']
    for item in expression:
        if not (item.isdigit() or item in valid_characters):
            return True
    return False
