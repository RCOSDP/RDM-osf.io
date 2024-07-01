'use-strict';

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

$('#upload-button').click(function() {
    // Clear file data before trigger file event
    $('#file-upload').val('');
    // Trigger input[type='file'] click event
    $('#file-upload').click();
});

$('#file-upload').change(function() {
    var files = $('#file-upload').prop('files');
    if (files && files.length > 0) {
        var uploadFile = files[0];
        var jsonExtensionRegex = new RegExp('\\.json$');
        if (!uploadFile.name.match(jsonExtensionRegex)) {
            $osf.growl('Error', _('Not a JSON file.'), 'danger', 5000);
            return;
        }
        var formData = new FormData();
        formData.append('file', uploadFile);
        $.ajax({
            url: 'setting',
            type: 'POST',
            data: formData,
            // Set processData to false to avoid processing file data
            processData: false,
            // Set contentType to false to avoid adding "Content-Type" header in "multipart/form-data" request
            contentType: false,
            success: function(json) {
                // Reload the page
                window.location.reload();
            },
            error: function(jqXHR) {
                var data = jqXHR.responseJSON;
                if (data && data['message']) {
                    // If response has message, show that message
                    $osf.growl('Error', _(data['message']), 'danger', 5000);
                } else if (jqXHR.status === 500) {
                    // If status is 500, show error message 'A server error occurred. Please contact the administrator.'
                    $osf.growl('Error', 'A server error occurred. Please contact the administrator.', 'danger', 5000);
                } else {
                    // Otherwise, show default error message
                    $osf.growl('Error', _('Some errors occurred'), 'danger', 5000);
                }
            }
        });
    }
});
