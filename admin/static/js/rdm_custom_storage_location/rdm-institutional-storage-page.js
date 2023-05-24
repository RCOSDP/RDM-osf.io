'use strict';

var $ = require('jquery');
var $osf = require('js/osfHelpers');
var Cookie = require('js-cookie');
var bootbox = require('bootbox');

var _ = require('js/rdmGettext')._;
var sprintf = require('agh.sprintf').sprintf;

var clipboard = require('js/clipboard');

var no_storage_name_providers = ['osfstorage', 'onedrivebusiness'];
// type1: get from admin/rdm_addons/api_v1/views.py
var preload_accounts_type1 = ['dropboxbusiness'];
// type2: get from admin/rdm_custom_storage_location/views.py
var preload_accounts_type2 = ['nextcloudinstitutions',
                'ociinstitutions',
                's3compatinstitutions']

var NAME_CURRENT = null;
var NEW_NAME_CURRENT = null;
var ATTRIBUTE_LIST = [
    'mail',
    'sn',
    'o',
    'ou',
    'givenName',
    'displayName',
    'eduPersonAffiliation',
    'eduPersonPrincipalName',
    'eduPersonEntitlement',
    'eduPersonScopedAffiliation',
    'eduPersonTargetedID',
    'eduPersonAssurance',
    'eduPersonUniqueId',
    'eduPersonOrcid',
    'isMemberOf',
    'jasn',
    'jaGivenName',
    'jaDisplayName',
    'jao',
    'jaou',
    'gakuninScopedPersonalUniqueCode',
]

function preload(provider, callback) {
    if (preload_accounts_type1.indexOf(provider) >= 0) {
        var div = $('#' + provider + '_authorization_div');
        var institutionId = div.data('institution-id');
        getAccount(provider, institutionId);
        if (provider === 'dropboxbusiness') {
            getAccount('dropboxbusiness_manage', institutionId);
        }
        if (callback) {
            callback();
        }
    } else if (preload_accounts_type2.indexOf(provider) >= 0) {
        // getCredentials(provider, callback);
 	getCredentials(provider, null);
        if (callback) {
            callback();
        }
    } else {
        if (callback) {
            callback();
        }
    }
}

function disable_storage_name(provider) {
    $('#storage_name').attr('disabled',
			    no_storage_name_providers.indexOf(provider) >= 0);
}

function selectedProvider() {
    return $('select[name=\'options\']').val();
}

$(window).on('load', function () {
    var provider = selectedProvider();
    disable_storage_name(provider);
    preload(provider, null);
});

$('[name=options]').change(function () {
    var provider = this.value;
    disable_storage_name(provider);
    preload(provider, null);
});

$('.modal').on('hidden.bs.modal', function (e) {
    $('body').css('overflow', 'auto');
});

function toggle_button(element) {
    element.classList.toggle('checked');
    element.value = element.classList.contains('checked') ? 'on' : 'off';
    element.checked = true;
}

$('button[type=reset]').click(function () {
    // reset allow checkbox
    var id = this.dataset.id;
    resetCheckbox('allow_checkbox', 'allow', id);
    resetCheckbox('readonly_checkbox', 'readonly', id);
    NEW_NAME_CURRENT = null;
    NAME_CURRENT = null;
});

$('button[data-dismiss="modal"]').click(function () {
    NEW_NAME_CURRENT = null;
    NAME_CURRENT = null;
});

$('.change_allow').change(function () {
    var is_allow = this.classList.contains('checked');
    var id = this.dataset.id;
    changeStatusExpression('allow', id, !is_allow);
    toggle_button(this);
});

$('.change_readonly').change(function () {
    var is_readonly = this.classList.contains('checked');
    var id = this.dataset.id;
    changeStatusExpression('readonly', id, !is_readonly);
    toggle_button(this);
});

$("#storage_name, input[name*='attribute_value'], input[name*='attribute'], .storage_input_value").on('keyup', function(e){
    var value = e.target.value;
    if (value.trim()) {
        e.target.setCustomValidity('');
    } else {
        e.target.setCustomValidity(_('This field is required.'));
    }
    e.target.reportValidity();
});

$("input[name*='attribute_value'], input[name*='attribute']").on('input', function(e) {
    var length = e.target.value.length;
    if (length >= 30) {
        e.target.title = e.target.value;
    } else {
        e.target.title = '';
    }
});

$('#attribute_authentication').change(function () {
    var is_attribute_authentication = !($(this).val() === 'on');
    var params = {
        'is_active': is_attribute_authentication
    };
    ajaxRequest(params, '', 'change_attribute_authentication', toggle_button, this);
});

$('#storage_name').on('keyup', function(e){
    var value = e.target.value;
    if (value.trim()) {
        e.target.setCustomValidity('');
    } else {
        e.target.setCustomValidity(e.target.dataset.title);
    }
    e.target.reportValidity();
});

$('#add_storage').click(function (e) {
    NEW_NAME_CURRENT = null;
    NAME_CURRENT = null;
    var storageNameElement = document.getElementById('storage_name');
    var value = storageNameElement.value.trim();
    if (value || (!value && storageNameElement.disabled)) {
        var provider = selectedProvider();

        preload(provider, null);
        var showModal = function () {
            $('#' + provider + '_modal').modal('show');
            $('body').css('overflow', 'hidden');
            $('.modal').css('overflow', 'auto');
            validateRequiredFields(provider);
        };
        if (provider === 'osfstorage') {
            showModal();
        } else {
            $osf.confirmDangerousAction({
                title: _('Are you sure you want to add institutional storage?'),
                callback: showModal,
                buttons: {
                    success: {
                        label: _('Change')
                    }
                }
            });
        }
        e.preventDefault();
    } else {
        storageNameElement.setCustomValidity(storageNameElement.dataset.title);
        storageNameElement.reportValidity();
    }
});

$('.storage_input_value').on('keyup', function(e){
    var value = e.target.value;
    if (value.trim()) {
        e.target.setCustomValidity('');
    } else {
        e.target.setCustomValidity(e.target.dataset.title);
    }
    e.target.reportValidity();
});

$('.save_button').click(function (e) {
    var id = this.dataset.id;
    var storageNameElement = document.getElementById('storage_name_' + id);
    var storageName = storageNameElement.value.trim();
    if (storageName || !storageName && storageNameElement.disabled) {
        var allowExpressionElement = document.getElementById('allow_' + id);
        var readonlyExpressionElement = document.getElementById('readonly_' + id);
        var allowCheckboxElement = document.getElementById('allow_checkbox_' + id);
        var readonlyCheckboxElement = document.getElementById('readonly_checkbox_' + id);
        var params = {
            'region_id': id,
            'allow': allowCheckboxElement.value === 'on' ? true : false,
            'readonly': readonlyCheckboxElement.value === 'on' ? true : false,
            'allow_expression': allowExpressionElement.value.trim(),
            'readonly_expression': readonlyExpressionElement.value.trim(),
            'storage_name': storageName.trim()
        }
        ajaxRequest(params, null, 'save_institutional_storage', null, this);
    } else {
        storageNameElement.setCustomValidity(_('This field is required.'));
        storageNameElement.reportValidity();
    }
});

$('#btn_add_attribute_form').click(function (e) {
    if (checkAuthenticationAttribute()) {
        ajaxRequest(null, null, 'add_attribute_form', null, this);
    } else {
        this.blur();
    }
})

$('.delete_attribute').click(function (e) {
    if (checkAuthenticationAttribute()) {
        var id = this.getAttribute('index_attribute');
        var params = {
            'id': id
        };
        ajaxRequest(params, null, 'delete_attribute_form', null, this);
    } else {
        this.blur();
    }
})

$('.save_attribute').click(function (e) {
    if (checkAuthenticationAttribute()) {
        var id = this.getAttribute('index_attribute');
        var attributeNameElement = document.getElementsByClassName('attribute_' + id)[0];
        var attributeValueElement = document.getElementsByClassName('attribute_value_' + id)[0];
        var attributeName = attributeNameElement.value.trim();
        var attributeValue = attributeValueElement.value.trim();
        var is_submitted = true;

        if (!attributeValue) {
            is_submitted = false;
            attributeValueElement.setCustomValidity(_('This field is required.'));
            attributeValueElement.reportValidity();
        }

        if (!attributeName) {
            is_submitted = false;
            attributeNameElement.setCustomValidity(_('This field is required.'));
        }
        else if (!ATTRIBUTE_LIST.includes(attributeName)) {
            is_submitted = false;
            attributeNameElement.setCustomValidity(_('No matches found.'));
        }
        attributeNameElement.reportValidity();

        if (is_submitted) {
            var params = {
                'id': id,
                'attribute': attributeName,
                'attribute_value': attributeValue
            };
            ajaxRequest(params, null, 'save_attribute_form', null, this);
        }
    } else {
        this.blur();
    }
})

$(".attribute_name").autocomplete({
    source: ATTRIBUTE_LIST,
    select: function(event, ui) {
        var selected_value = ui.item.value;
        if (selected_value.length >= 30) {
            $(this)[0].title = selected_value;
        } else {
            $(this)[0].title = '';
        }
    }
});

$(".attribute_name").on('keydown', function(e) {
    var keyCode = e.keyCode || e.which;
    if (keyCode == 9) {
        e.preventDefault();
        var id = this.getAttribute('id');
        if (!ATTRIBUTE_LIST.includes(this.value)) {
            var firstItem = $("#ui-id-" + id[id.length - 1] + " .ui-menu-item").first().text();
            $(this).val(firstItem);
        }
    }
    var value = e.target.value;
    if (value.length >= 30) {
        this.setAttribute('title', value);
    } else {
        this.setAttribute('title', '');
    }
});

$('#s3_modal input').keyup(function () {
    validateRequiredFields('s3');
});

$('#s3_modal input').on('paste', function(e) {
    validateRequiredFields('s3');
});

$('#s3compat_modal input').keyup(function () {
    validateRequiredFields('s3compat');
});

$('#s3compat_modal input').on('paste', function(e) {
    validateRequiredFields('s3compat');
});

$('#s3compatinstitutions_modal input').keyup(function () {
    validateRequiredFields('s3compatinstitutions');
});

$('#s3compatinstitutions_modal input').on('paste', function(e) {
    validateRequiredFields('s3compatinstitutions');
});

$('#ociinstitutions_modal input').keyup(function () {
    validateRequiredFields('ociinstitutions');
});

$('#ociinstitutions_modal input').on('paste', function(e) {
    validateRequiredFields('ociinstitutions');
});

$('#swift_modal input').keyup(function () {
    validateRequiredFields('swift');
});

$('#swift_modal input').on('paste', function(e) {
    validateRequiredFields('swift');
});

$('#owncloud_modal input').keyup(function () {
    validateRequiredFields('owncloud');
});

$('#owncloud_modal input').on('paste', function(e) {
    validateRequiredFields('owncloud');
});

$('#nextcloud_modal input').keyup(function () {
    validateRequiredFields('nextcloud');
});

$('#nextcloud_modal input').on('paste', function(e) {
    validateRequiredFields('nextcloud');
});

$('#nextcloudinstitutions_modal input').keyup(function () {
    validateRequiredFields('nextcloudinstitutions');
});

$('#nextcloudinstitutions_modal input').on('paste', function(e) {
    validateRequiredFields('nextcloudinstitutions');
});

$('#googledrive_modal input').keyup(function () {
    authSaveButtonState('googledrive');
});

$('#googledrive_modal input').on('paste', function(e) {
    authSaveButtonState('googledrive');
});

$('#box_modal input').keyup(function () {
    authSaveButtonState('box');
});

$('#box_modal input').on('paste', function(e) {
    authSaveButtonState('box');
});

$('#onedrivebusiness_modal input').keyup(function () {
    authSaveButtonState('onedrivebusiness');
});

$('#onedrivebusiness_modal input').on('paste', function(e) {
    authSaveButtonState('onedrivebusiness');
});

function strip_last_slash(s) {
    return s.replace(/\/+$/g, '');
}

function nextcloudinstitutions_host() {
    // url.rstrip('/') in admin/rdm_custom_storage_location/utils.py
    return 'https://' + strip_last_slash($('#nextcloudinstitutions_host').val());
}

function update_nextcloudinstitutions_notification_connid() {
    var connid = nextcloudinstitutions_host() + ':' + $('#nextcloudinstitutions_username').val();
    $('#nextcloudinstitutions_notification_connid').attr('value', connid);
    clipboard('#copy_button_connid');
}

function update_nextcloudinstitutions_notification_url() {
    var osf_domain = strip_last_slash($('#osf_domain').val());
    var url = osf_domain + '/api/v1/addons/nextcloudinstitutions/webhook/';
    $('#nextcloudinstitutions_notification_url').attr('value', url);
    clipboard('#copy_button_url');
}

$('#nextcloudinstitutions_host').on('keyup paste', function () {
    update_nextcloudinstitutions_notification_connid();
    update_nextcloudinstitutions_notification_url();
});
$('#nextcloudinstitutions_username').on('keyup paste', function () {
    update_nextcloudinstitutions_notification_connid();
});

$('#csv_file').on('change', function() {
    var filename = '';
    var fileLists = $(this).prop('files');
    if (fileLists.length > 0) {
        filename = $(this).prop('files')[0].name;
    }
    $('#csv_file_name').text(filename);
});

function validateRequiredFields(providerShortName) {
    // Check if all the inputs are filled, so we can enable the connect button
    var allFilled = $('#' + providerShortName + '_modal [required]').toArray().reduce(function (accumulator, current) {
        return accumulator && current.value.length > 0;
    }, true);
    $('#' + providerShortName + '_connect').attr('disabled', !allFilled);
}

$('#swift_auth_version').change(function () {
    var swiftKeystoneVersion = $(this).val();
    if (swiftKeystoneVersion === '2') {
        $('#swift_project_domain_name').attr('disabled', true);
        $('#swift_user_domain_name').attr('disabled', true);
        $('#swift_project_domain_name').attr('required', false);
        $('#swift_user_domain_name').attr('required', false);
    } else {
        $('#swift_project_domain_name').attr('disabled', false);
        $('#swift_user_domain_name').attr('disabled', false);
        $('#swift_project_domain_name').attr('required', true);
        $('#swift_user_domain_name').attr('required', true);
    }
    validateRequiredFields('swift');
});

function disableButtons(providerShortName) {
    $('#' + providerShortName + '_connect').attr('disabled', true);
    $('#' + providerShortName + '_save').attr('disabled', true);
}

function have_csv_ng() {
    var csv_ng = $('#csv_ng');
    return csv_ng.length && csv_ng.text().length && csv_ng.text() !== 'NG=0';
}

$('.test-connection').click(function () {
    buttonClicked(this, 'test_connection');
});

$('.save-credentials').click(function () {
    buttonClicked(this, 'save_credentials');
});

function buttonClicked(button, route) {
    var action = {
        'test_connection': 'connect',
        'save_credentials': 'save',
    };

    var providerShortName = $(button).attr('id').replace('_' + action[route], '');
    if (have_csv_ng()) {
        disableButtons(providerShortName);
	return;
    }

    var params = {
        'provider_short_name': providerShortName,
        'new_storage_name': '',
        'storage_name': '',
    };
    getParameters(params);
    if (NEW_NAME_CURRENT != null) {
        params.new_storage_name = NEW_NAME_CURRENT;
        params.storage_name = NAME_CURRENT;
    }
    ajaxRequest(params, providerShortName, route, null);
}

var csrftoken = $('[name=csrfmiddlewaretoken]').val()

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

function ajaxCommon(type, params, providerShortName, route, callback, element) {
    if (type === 'POST') {
      params = JSON.stringify(params);
    }
    $.ajax({
        url: '../' + route + '/',
        type: type,
        data: params,
        contentType: 'application/json; charset=utf-8',
        custom: providerShortName,
        timeout: 120000,
        success: function (data) {
            afterRequest[route].success(this.custom, data);
            if (callback) {
                callback(element);
            }
        },
        error: function (jqXHR) {
            if(jqXHR.responseJSON != null && ('message' in jqXHR.responseJSON)){
                afterRequest[route].fail(this.custom, jqXHR.responseJSON.message);
            }else{
                afterRequest[route].fail(this.custom, _('Some errors occurred'));
            }
            if (callback) {
                callback(element);
            }
        }
    });
}

function ajaxGET(params, providerShortName, route, callback) {
    ajaxCommon('GET', params, providerShortName, route, callback);
}

// ajaxPOST
function ajaxRequest(params, providerShortName, route, callback, element) {
    ajaxCommon('POST', params, providerShortName, route, callback, element);
}

var afterRequest = {
    'test_connection': {
        'success': function (id, data) {
            $('#' + id + '_save').attr('disabled', false);
            $('#' + id + '_save').removeClass('btn-default').addClass('btn-success');
            $('#' + id + '_connect').removeClass('btn-success').addClass('btn-default');
            $('#' + id + '_message').html(_(data.message));
            if (!$('#' + id + '_message').hasClass('text-success')) {
                $('#' + id + '_message').addClass('text-success');
                $('#' + id + '_message').removeClass('text-danger');
            }
        },
        'fail': function (id, message) {
            $('#' + id + '_message').html(_(message));
            $('#' + id + '_save').attr('disabled', true);
            $('#' + id + '_save').removeClass('btn-success').addClass('btn-default');
            $('#' + id + '_connect').removeClass('btn-default').addClass('btn-success');
            if (!$('#' + id + '_message').hasClass('text-danger')) {
                $('#' + id + '_message').addClass('text-danger');
                $('#' + id + '_message').removeClass('text-success');
            }
        }
    },
    'save_credentials': {
        'success': function (id, data) {
            $('#' + id + '_message').html(data.message);
            $('.modal').modal('hide');
            $('#' + id + '_message').addClass('text-success');
            $('#' + id + '_message').removeClass('text-danger');
            location.reload(true);
        },
        'fail': function (id, message) {
            $('#' + id + '_message').html(message);
            $('#' + id + '_save').attr('disabled', true);
            $('#' + id + '_save').removeClass('btn-success').addClass('btn-default');
            $('#' + id + '_connect').removeClass('btn-default').addClass('btn-success');
            if (!$('#' + id + '_message').hasClass('text-danger')) {
                $('#' + id + '_message').addClass('text-danger');
                $('#' + id + '_message').removeClass('text-success');
            }
        }
    },
    'change_attribute_authentication': {
        'success': function (id, data) {
            location.reload(true);
        },
        'fail': function (id, message) {
            $osf.growl(_('Error'), _(message));
        }
    },
    'add_attribute_form': {
        'success': function (id, data) {
            location.reload(true);
        },
        'fail': function (id, message) {
            $osf.growl(_('Error'), _(message), 'danger', 5000);
        }
    },
    'delete_attribute_form': {
        'success': function (id, data) {
            location.reload(true);
        },
        'fail': function (id, message) {
            $osf.growl(_('Error'), _(message), 'danger', 5000);
        }
    },
    'save_attribute_form': {
        'success': function (id, data) {
            location.reload(true);
        },
        'fail': function (id, message) {
            $osf.growl(_('Error'), _(message), 'danger', 5000);
        }
    },
    'save_institutional_storage': {
        'success': function (id, data) {
            location.reload(true);
        },
        'fail': function (id, message) {
            $osf.growl(_('Error'), _(message), 'danger', 5000);
        }
    },
    'credentials': {
        'success': function (id, data) {
            setParameters(id, data);
        },
        'fail': function (id, message) {
            setParametersFailed(id, message);
        }
    },
    'fetch_temporary_token': {
        'success': function (id, data) {
            var response_data = data.response_data;
            authPermissionSucceed(id, response_data.fullname, response_data.oauth_key);
        },
        'fail': function (id, message) {
            authPermissionFailed(id, message);
        }
    },
    'remove_auth_data_temporary': {
        'success': function (id, data) {
            authPermissionFailed(id, data.message);
        },
        'fail': function (id, message) {
            authPermissionFailed(id, message);
        }
    },
    'usermap': {
        'success': function (id, data) {
            usermapDownload(id, data);
        },
        'fail': function (id, message) {
            usermapDownloadFailed(id, message);
        }
    },
};

function checkAuthenticationAttribute() {
    return $('#attribute_authentication').val() === 'on';
}

function changeStatusExpression(type, id, chekboxValue) {
    if (checkAuthenticationAttribute()) {
        var expressionElement = document.getElementById(type + '_' + id);
        expressionElement.disabled = chekboxValue ? false : true;
    }
}

function resetCheckbox(typeCheckbox, typeExpression, id) {
    var allowCheckboxElement = document.getElementById(typeCheckbox +  '_' + id);
    var allowExpressionElement = document.getElementById(typeExpression + '_' + id);
    if (allowCheckboxElement.dataset.value == 'true') {
        allowCheckboxElement.classList.add('checked');
        changeStatusExpression(typeExpression, id, true);
    }
    else {
        allowCheckboxElement.classList.remove('checked');
        changeStatusExpression(typeExpression, id, false);
    }
}

function getParameters(params) {
    var providerClass = params.provider_short_name + '-params';
    var allParameters = $('.' + providerClass);
    params.storage_name = $('#storage_name').val();
    $.each(allParameters, function (key, value) {
        if (!value.disabled) {
            params[value.id] = value.value;
        }
    });
}

function authoriseOnClick(elm) {
    var providerShortName = elm.id.replace('_auth_hyperlink', '');
    var institutionId = $(elm).data('institution-id');
    oauthOpener(elm.href, providerShortName, institutionId);
}

$('.auth-permission-button').click(function(e) {
    $(this).click(false);
    $(this).addClass('disabled');
    authoriseOnClick(this);
    e.preventDefault();
});

function disconnectOnClick(elm, properName, accountName) {
    var providerShortName = elm.id.replace('_disconnect_hyperlink', '');
    var institutionId = $(elm).data('institution-id');

    var deletionKey = Math.random().toString(36).slice(-8);
    var id = providerShortName + "DeleteKey";
    bootbox.confirm({
        title: _('Disconnect Account?'),
        message: '<p class="overflow">' +
            sprintf(_('Are you sure you want to disconnect the %1$s account <strong>%2$s</strong>?<br>'), $osf.htmlEscape(properName), $osf.htmlEscape(accountName)) +
            sprintf(_('This will revoke access to %1$s for all projects using this account.<br><br>'), $osf.htmlEscape(properName)) +
            sprintf(_("Type the following to continue: <strong>%1$s</strong><br><br>"), $osf.htmlEscape(deletionKey)) +
            "<input id='" + $osf.htmlEscape(id) + "' type='text' class='bootbox-input bootbox-input-text form-control'>" +
            '</p>',
        callback: function(confirm) {
            if (confirm) {
                if ($('#'+id).val() == deletionKey) {
                    disconnectAccount(providerShortName, institutionId);
                } else {
                    $osf.growl('Verification failed', 'Strings did not match');
                }
            } else {
                $(elm).removeClass('disabled');
            }
        },
        buttons:{
            confirm:{
                label:_('Disconnect'),
                className:'btn-danger'
            }
        }
    });
}

$('.auth-cancel').click(function(e) {
    var providerShortName = this.id.replace('_cancel', '');
    authPermissionFailed(providerShortName, '');
    var route = 'remove_auth_data_temporary';
    cancel_auth(providerShortName);
});


function get_token(providerShortName, route) {
    var params = {
        'provider_short_name': providerShortName
    };
    ajaxRequest(params, providerShortName, route, null);
}

function getCredentials(providerShortName, callback) {
    var params = {
        'provider_short_name': providerShortName
    };
    var route = 'credentials';
    // ajaxRequest(params, providerShortName, route, callback);
    ajaxGET(params, providerShortName, route, callback);
}

function setParameters(provider_short_name, data) {
    var providerClass = provider_short_name + '-params';
    $('.' + providerClass).each(function(i, e) {
        var val = data[$(e).attr('id')];
	if (val) {
            $(e).val(val);
        }
    });

    if (provider_short_name === 'nextcloudinstitutions') {
	update_nextcloudinstitutions_notification_connid();
	update_nextcloudinstitutions_notification_url();
    }
}

function setParametersFailed(provider_short_name, message) {
}

function getAccount(providerShortName, institutionId) {
    // get an External Account for Institutions
    var url = '/addons/api/v1/settings/' + providerShortName + '/' + institutionId + '/accounts/';
    var request = $.get(url);
    request.done(function (data) {
        if (data.accounts.length > 0) {
            authPermissionSucceedWithoutToken(providerShortName, data.accounts[0].display_name);
            $('#' + providerShortName + '_auth_hyperlink').addClass('disabled');
            var link = $('#' + providerShortName + '_disconnect_hyperlink');
            link.click(false);
            link.off();
            link.click(function (e) {
                $(this).click(false);
                $(this).addClass('disabled');
                disconnectOnClick(this, data.accounts[0].provider_name, data.accounts[0].display_name);
                e.preventDefault();
            });
            link.removeClass('disabled');
            $('.' + providerShortName + '-disconnect-callback').removeClass('hidden');
        } else {
            var link = $('#' + providerShortName + '_auth_hyperlink');
            link.off();
            link.click(function (e) {
                $(this).click(false);
                $(this).addClass('disabled');
                authoriseOnClick(this);
                e.preventDefault();
            });
            link.removeClass('disabled');
            $('#' + providerShortName + '_authorization_div').addClass('hidden');
            $('.' + providerShortName + '-disconnect-callback').addClass('hidden');
        }
    }).fail(function (data) {
        if ('message' in data) {
            authPermissionFailedWithoutToken(providerShortName, data.message);
        } else {
            authPermissionFailedWithoutToken(providerShortName, _('Some errors occurred'));
        }
    });
}

function disconnectAccount(providerShortName, institutionId) {
    var url = '/addons/api/v1/settings/' + providerShortName + '/' + institutionId + '/accounts/';
    var request = $.get(url);
    request.then(function (data) {
        url = '/addons/api/v1/oauth/accounts/' + data.accounts[0].id + '/' + institutionId + '/';
        var request2 = $.ajax({
            url: url,
            type: 'DELETE'
        });
    }).then(
        function () {
            getAccount(providerShortName, institutionId);
        }
    );
}

function oauthOpener(url,providerShortName,institutionId){
    var win = window.open(
        url,
        'OAuth');
    var params = {
        'provider_short_name': providerShortName
    };
    var route = 'fetch_temporary_token';
    var timer = setInterval(function() {
        if (win.closed) {
            clearInterval(timer);
            if (providerShortName === 'dropboxbusiness' ||
                providerShortName === 'dropboxbusiness_manage') {
                getAccount(providerShortName, institutionId);
            } else {
                get_token(providerShortName, route);
            }
        }
    }, 1000, [providerShortName, route]);
}

function authPermissionSucceed(providerShortName, authorizedBy, currentToken){
    var providerClass = providerShortName + '-auth-callback';
    var allFeedbackFields = $('.' + providerClass);
    allFeedbackFields.removeClass('hidden');
    $('#' + providerShortName + '_authorized_by').text(authorizedBy);
    $('#' + providerShortName + '_current_token').text('********');
    authSaveButtonState(providerShortName);
}

function authPermissionSucceedWithoutToken(providerShortName, authorizedBy){
    var providerClass = providerShortName + '-auth-callback';
    var allFeedbackFields = $('.' + providerClass);
    allFeedbackFields.removeClass('hidden');
    $('#' + providerShortName + '_authorized_by').text(authorizedBy);
}

function authPermissionFailed(providerShortName, message){
    var providerClass = providerShortName + '-auth-callback';
    var allFeedbackFields = $('.' + providerClass);
    allFeedbackFields.addClass('hidden');
    $('#' + providerShortName + '_authorized_by').text('');
    $('#' + providerShortName + '_current_token').text('');
    $('#' + providerShortName + '_auth_hyperlink').attr('disabled', false);
    $('#' + providerShortName + '_auth_hyperlink').removeClass('disabled');
    authSaveButtonState(providerShortName);
}

function authPermissionFailedWithoutToken(providerShortName, message){
    var providerClass = providerShortName + '-auth-callback';
    var allFeedbackFields = $('.' + providerClass);
    allFeedbackFields.addClass('hidden');
    $('#' + providerShortName + '_authorized_by').text('');
    $('#' + providerShortName + '_auth_hyperlink').attr('disabled', false);
    $('#' + providerShortName + '_auth_hyperlink').removeClass('disabled');
}

function authSaveButtonState(providerShortName) {
    var is_folder_valid = $('#' + providerShortName + '_folder').val() !== '';
    var is_token_valid = $('#' + providerShortName + '_current_token').text().length>0;
    $('#' + providerShortName + '_save').attr('disabled', !(is_folder_valid && is_token_valid));
}

function cancel_auth(providerShortName) {
    var params = {
        'provider_short_name': providerShortName
    };
    var route = 'remove_auth_data_temporary';
    ajaxRequest(params, providerShortName, route, null);
}

function reflect_csv_results(data, providerShortName) {
    $('#csv_ok').html('OK=' + data.OK);
    $('#csv_ng').html('NG=' + data.NG);
    $('#csv_report').html(data.report.join('<br/>'));
    $('#csv_usermap').html(JSON.stringify(data.user_to_extuser));

    if (have_csv_ng()) {
        disableButtons(providerShortName);
    } else {
        validateRequiredFields(providerShortName);
    }
}

$('#csv_file').change(function () {
    var provider = selectedProvider();
    var file = $(this).prop('files')[0];

    var fd = new FormData();
    fd.append('provider', provider);
    if (file === undefined) {  // unselected
        fd.append('clear', true);
    } else {
        fd.append($(this).attr('name'), file);
        var providerClass = provider + '-params';
        $('.' + providerClass).each(function(i, e) {
             fd.append($(e).attr('id'), $(e).val());
        });
        fd.append('check_extuser', $('#csv_check_extuser').is(':checked'));
    }
    $.ajax({
        url: '../usermap/',
        type: 'POST',
        data: fd,
        processData: false,
        contentType: false,
        timeout: 30000
    }).done(function (data) {
	reflect_csv_results(data, provider);
    }).fail(function (jqXHR) {
        if (jqXHR.responseJSON != null) {
            reflect_csv_results(jqXHR.responseJSON, provider);
        } else {
            $('#csv_ok').html('');
            $('#csv_ng').html(_('Some errors occurred'));
            $('#csv_report').html('');
            $('#csv_usermap').html('');
        }
    });
});

$('.download-csv').click(function () {
    var provider = selectedProvider()
    var params = {
        'provider': provider
    };
    $('#csv_download_ng').html('');
    ajaxGET(params, provider, 'usermap', null)
});

function saveFile(filename, type, content) {
    if (window.navigator.msSaveOrOpenBlob) {
        var blob = new Blob([content], {type: type});
        window.navigator.msSaveOrOpenBlob(blob, filename);
    }
    else {
        var element = document.createElement('a');
        element.setAttribute('href', 'data:' + type + ',' + encodeURIComponent(content));
        element.setAttribute('download', filename);
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    }
}

function usermapDownload(id, data) {
    var name = 'usermap-' + selectedProvider() +'.csv';
    saveFile(name, 'text/csv; charset=utf-8', data);
}

function usermapDownloadFailed(id, message) {
    $('#csv_download_ng').html(message);
}
