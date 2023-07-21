'use strict';
var m = require('mithril');
var iconmap = require('js/iconmap');
var Treebeard = require('treebeard');

var _ = require('js/rdmGettext')._;

require('../css/fangorn.css');

function resolveToggle(item) {
    var toggleMinus = m('i.fa.fa-minus', ' ');
    var togglePlus = m('i.fa.fa-plus', ' ');

    if (item.children.length > 0) {
        if (item.open) {
            return toggleMinus;
        }
        return togglePlus;
    }
    item.open = true;
    return '';
}

function resolveIcon(item) {
    var icons = iconmap.projectComponentIcons;
    function returnView(category) {
        return m('span', { 'class' : icons[category]});
    }
    if (item.data.kind === 'component' && item.parent().data.title === 'Component Wiki Pages') {
        if(item.data.pointer) {
            return m('i.fa.fa-link', '');
        }
        return returnView(item.data.category);
    }
    if (item.data.type === 'heading' || item.data.kind === 'folder') {
        if (item.open) {
            return m('i.fa.fa-folder-open', ' ');
        }
        return m('i.fa.fa-folder', ' ');
    }
    return m('i.fa.fa-file-o', ' ');
}

function openParentFolders (item) {
    var tb = this;
    // does it have a parent? If so change open
    var parent = item.parent();
    if (parent) {
        if (!parent.open) {
            var index = tb.returnIndex(parent.id);
            parent.load = true;
            tb.toggleFolder(index);
        }
        openParentFolders.call(tb, parent);
    }
}

function WikiMenu(data, wikiID, canEdit) {

    //  Treebeard version
    var tbOptions = {
        divID: 'grid',
        filesData: data,
        paginate : false,       // Whether the applet starts with pagination or not.
        paginateToggle : false, // Show the buttons that allow users to switch between scroll and paginate.
        uploads : false,         // Turns dropzone on/off.
        hideColumnTitles: true,
        resolveIcon : resolveIcon,
        resolveToggle : resolveToggle,
        columnTitles: function () {
            return[{
                title: _('Name'),
                width: '100%'
            }];
        },
        ondataload: function() {
            var tb = this;  // jshint ignore: line
            for (var i = 0; i < tb.treeData.children.length; i++) {
                var parent = tb.treeData.children[i];
                if (parent.data.title === 'Project Wiki Pages') {
                    tb.updateFolder(null, parent);
                }
            }
        },
        resolveRows : function (item){
            var tb = this;
            var columns = [];
            if(item.data.type === 'heading') {
                columns.push({
                    folderIcons: true,
                    custom: function() {
                        return m('b', _(item.data.title));
                    }
                });
            } else {
                if(item.data.page.id === wikiID) {
                    item.css = 'fangorn-selected';
                    tb.multiselected([item]);
                    openParentFolders(item);
                }
                columns.push({
                    folderIcons: true,
                    custom: function() {
                        return m('a.fg-file-links', {href: item.data.page.url}, _(item.data.page.name));
                    }
                });
            }
            return columns;
        },
        hScroll: 500,
        showFilter : false,     // Gives the option to filter by showing the filter box.
        allowMove : false,       // Turn moving on or off.
        hoverClass : 'fangorn-hover',
        resolveRefreshIcon : function() {
            return m('i.fa.fa-refresh.fa-spin');
        }
    };


    
    var grid = new Treebeard(tbOptions);
}

module.exports = WikiMenu;
