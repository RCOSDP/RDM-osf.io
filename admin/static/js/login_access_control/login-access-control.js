'use strict';

var $ = require('jquery');
var $osf = require('js/osfHelpers');
var _ = require('js/rdmGettext')._;

var csrftoken = $('[name=csrfmiddlewaretoken]').val();

function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

$.ajaxSetup({
    crossDomain: false,
    beforeSend: function (xhr, settings) {
        if (!csrfSafeMethod(settings.type)) {
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
        }
    }
});

function postAJAX(url, params, callback) {
    $.ajax({
        url: url,
        type: 'POST',
        data: JSON.stringify(params),
        contentType: 'application/json; charset=utf-8',
        timeout: 120000,
        success: function (data) {
            if (callback) {
                callback();
            } else {
                window.location.reload();
            }
        },
        error: function (jqXHR) {
            if (jqXHR.status === 500) {
                // If status is 500, show error message 'A server error occurred. Please contact the administrator.'
                $osf.growl(_('Error'), jqXHR.responseText, 'danger', 5000);
            } else if (jqXHR.responseJSON != null && 'error_message' in jqXHR.responseJSON) {
                $osf.growl(_('Error'), _(jqXHR.responseJSON.error_message), 'danger', 5000);
            } else {
                $osf.growl(_('Error'), _('A server error occurred. Please contact the administrator.'), 'danger', 5000);
            }
        }
    });
}

function getNumberId(id, prefix) {
    return parseInt(id.replace(prefix, ''));
}

function setInvalidMessageForAttributeName(event) {
    event.target.setCustomValidity(_('Attribute name is required.'));
}

function setInvalidMessageForAttributeValue(event) {
    var element = event.target;
    element.setCustomValidity('');
    if (!!element.validity.valueMissing) {
        element.setCustomValidity(_('Attribute value is required.'));
    } else if (!!element.validity.tooLong) {
        element.setCustomValidity(_('Length of attribute value > 255 characters.'));
    }
}

function setInvalidMessageForMailAddress(event) {
    var element = event.target;
    element.setCustomValidity('');
    if (!!element.validity.valueMissing) {
        element.setCustomValidity(_('Mail address is required.'));
    } else if (!!element.validity.tooLong) {
        element.setCustomValidity(_('Length of mail address > 320 characters.'));
    } else if (!!element.validity.patternMismatch) {
        element.setCustomValidity(_('Mail address format is invalid.'));
    }
}

$(document).ready(function() {
    $('select[name="attribute_name"]').on('invalid', setInvalidMessageForAttributeName);
    $('input[name="attribute_value_input"]').on('invalid', setInvalidMessageForAttributeValue);
    $('input[name="mail_address_input"]').on('invalid', setInvalidMessageForMailAddress);
})

$('#loginAvailabilityDefaultForm').on('submit', function(event) {
    event.preventDefault();
    $('#toggleLoginAvailabilityDefaultModal').modal('hide');
    var params = {
        'institution_id': window.contextVars.institution_id,
        'login_availability_default': document.getElementById('loginAvailability').checked,
    };
    var url = './login_availability_default';
    postAJAX(url, params);
});

$('#authenticationAttributesForm').on('submit', function(event) {
    event.preventDefault();
    var attributeData = [];
    for (var i = 0; i < $("select[name='attribute_name']").length; i++) {
        var attributeName = $($("select[name='attribute_name']")[i]);
        var attributeNameInput = attributeName.val().trim();
        var attributeValue = $($("input[name='attribute_value_input']")[i]);
        var attributeValueInput = attributeValue.val().trim();

        attributeData.push({
            'attribute_name': attributeNameInput,
            'attribute_value': attributeValueInput
        });
    }

    var params = {
        'institution_id': window.contextVars.institution_id,
        'attribute_data': attributeData,
    };
    var url = './authentication_attribute/save';
    postAJAX(url, params);
});

$('input[name="toggleAuthenticationAttribute"]').on('change', function(event) {
    var params = {
        'institution_id': window.contextVars.institution_id,
        'attribute_id': getNumberId(event.target.id, 'toggle_authentication_attribute_'),
        'is_availability': event.target.checked,
    };
    var url = './authentication_attribute/update';
    postAJAX(url, params);
});

$('a[name="deleteAuthenticationAttribute"]').on('click', function(event) {
    var params = {
        'institution_id': window.contextVars.institution_id,
        'attribute_id': getNumberId(event.target.id, 'delete_authentication_attribute_'),
    };
    var url = './authentication_attribute/delete';
    postAJAX(url, params, function() {
        if (!!window.contextVars.attribute_length && window.contextVars.attribute_length <= 1) {
            var redirectUrl = '/login_access_control?institution_id=' + window.contextVars.institution_id;
            if (!!window.contextVars.authentication_attribute_page && window.contextVars.authentication_attribute_page > 1) {
                redirectUrl += '&attribute_page_number=' + (window.contextVars.authentication_attribute_page - 1);
                if (!!window.contextVars.mail_address_page) {
                    redirectUrl += '&mail_address_page_number=' + window.contextVars.mail_address_page;
                }
                window.location.href = redirectUrl;
                return;
            }
        }
        window.location.reload();
    });
});

$('#logicConditionForm').on('submit', function(event) {
    event.preventDefault();
    var params = {
        'institution_id': window.contextVars.institution_id,
        'logic_condition': $('#loginLogicCondition').val().trim(),
    };
    var url = './authentication_attribute/logic_condition';
    postAJAX(url, params);
});

$('#mailAddressForm').on('submit', function(event) {
    event.preventDefault();
    var mailAddressList = [];
    for (var i = 0; i < $("[name='mail_address_input']").length; i++) {
        var mailAddressElement = $($("[name='mail_address_input']")[i]);
        var mailAddressInput = mailAddressElement.val().trim();
        mailAddressList.push(mailAddressInput);
    }
    var params = {
        'institution_id': window.contextVars.institution_id,
        'mail_address_list': mailAddressList,
    };
    var url = './mail_address/save';
    postAJAX(url, params);
});

$('input[name="toggleMailAddress"]').on('change', function(event) {
    var params = {
        'institution_id': window.contextVars.institution_id,
        'mail_address_id': getNumberId(event.target.id, 'toggle_mail_address_'),
        'is_availability': event.target.checked,
    };
    var url = './mail_address/update';
    postAJAX(url, params);
});

$('a[name="deleteMailAddress"]').on('click', function(event) {
    var params = {
        'institution_id': window.contextVars.institution_id,
        'mail_address_id': getNumberId(event.target.id, 'delete_mail_address_'),
    };
    var url = './mail_address/delete';
    postAJAX(url, params, function() {
        if (!!window.contextVars.mail_address_length && window.contextVars.mail_address_length <= 1) {
            var redirectUrl = '/login_access_control?institution_id=' + window.contextVars.institution_id;
            if (!!window.contextVars.mail_address_page && window.contextVars.mail_address_page > 1) {
                if (!!window.contextVars.authentication_attribute_page) {
                    redirectUrl += '&attribute_page_number=' + window.contextVars.authentication_attribute_page;
                }
                redirectUrl += '&mail_address_page_number=' + (window.contextVars.mail_address_page - 1);
                window.location.href = redirectUrl;
                return;
            }
        }
        window.location.reload();
    });
});

$('#attributes_block').on('attribute_created', function() {
    $('select[name="attribute_name"]').on('invalid', setInvalidMessageForAttributeName);
    $('input[name="attribute_value_input"]').on('invalid', setInvalidMessageForAttributeValue);
});

$('#mail_addresses_block').on('mail_address_created', function() {
    $('input[name="mail_address_input"]').on('invalid', setInvalidMessageForMailAddress);
});
