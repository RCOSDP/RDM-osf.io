/**
 * Module for listing all projects/components authorized for a given addon
 * on the user settings page. Also handles revoking addon access from these
 * projects/components.
 */
'use strict';

var $ = require('jquery');
var bootbox = require('bootbox');

var $osf = require('js/osfHelpers');

var rdmGettext = require('js/rdmGettext');
var gt = rdmGettext.rdmGettext();
var _ = function(msgid) { return gt.gettext(msgid); };
var agh = require('agh.sprintf');

var AddonPermissionsTable = {
    init: function(addonShortName, addonFullname) {
        $('.' + addonShortName + '-remove-token').on('click', function (event) {
            var nodeId = $(this).attr('node-id');
            var apiUrl = $(this).attr('api-url')+ addonShortName + '/config/';
            bootbox.confirm({
                title: _('Remove addon?'),
                message: agh.sprintf(_('Are you sure you want to disconnnect the %1$s account from this project?'),$osf.htmlEscape(addonFullname)),
                callback: function (confirm) {
                    if (confirm) {
                        $.ajax({
                            type: 'DELETE',
                            url: apiUrl,

                            success: function (response) {

                                $('#' + addonShortName + '-' + nodeId + '-auth-row').hide();
                                var numNodes = $('#' + addonShortName + '-auth-table tr:visible').length;
                                if (numNodes === 1) {
                                    $('#' + addonShortName + '-auth-table').hide();
                                }
                                if (numNodes === 4) {
                                    $('#' + addonShortName + '-more').hide();
                                    $('#' + addonShortName+ '-less').hide();
                                }
                            },

                            error: function () {
                                $osf.growl(_('An error occurred, the account is still connected to the project. '),
                                    agh.sprintf(_('If the issue persists, please report it to %1$s.') , $osf.osfSupportLink()));
                            }
                        });
                    }
                },
                buttons:{
                    confirm:{
                        label:_('Remove'),
                        className:'btn-danger'
                    },
                    cancel:{
                        label:_('Cancel')
                    }
                }
            });
        });
    }
};

module.exports = AddonPermissionsTable;
