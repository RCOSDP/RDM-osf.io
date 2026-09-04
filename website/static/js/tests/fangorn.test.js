/*global describe, it, expect, example, before, after, beforeEach, afterEach, mocha, sinon*/
'use strict';

var testUtils = require('./utils');
var $osf = require('js/osfHelpers');
var Fangorn = require('js/fangorn');

var assert = require('chai').assert;
var utils = require('tests/utils');
var faker = require('faker');
var $ = require('jquery');
var Raven = require('raven-js');

window.contextVars = {
    osfSupportEmail : 'fake-support@osf.io',
    waterbutlerURL : 'https://files.osf.io/',
    threshold : 0.9,
};

var language = require('js/osfLanguage').projectSettings;


describe('fangorn', () => {
    describe('FangornMoveAndDeleteUnitTests', () => {
        // folder setup
        var folder;
        var item;
        var getItem = function(kind, id, name){
            if(typeof id === 'undefined'){
                id = 2;
            }
            if(typeof name === 'undefined'){
                name = kind + id;
            }
            return {
                'data': {
                    'provider': 'osfstorage',
                    'kind': kind,
                    'name': name,
                    'extra': {},
                    'permissions': {
                        'edit': true
                    }
                },
                'children': [],
                'id': id,
                'parentID': 1,
            };
        };
        describe('getCopyMode integration', () => {
            it('can be dropped and returns move if valid', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'move');
            });

            it('can be dropped and returns copy if github provider', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'github';
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'copy');
            });

            it('cannot be dropped if folder.data is undefined', () => {
                folder = getItem('file', 2);
                delete folder.data;
                item = getItem('file', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('cannot be dropped if isInvalidDropFolder returns true', () => {
                folder = getItem('file', 2);
                item = getItem('file', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('cannot be dropped if isInvalidDropItem returns true', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.nodeType = 'project';
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('cannot be dropped if dragging parent into child', () => {
                folder = getItem('folder', 2);
                item = getItem('folder', 3);
                item.children = [folder];
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('cannot be dropped if item inProgress is true', () => {
                folder = getItem('folder', 2);
                item = getItem('folder', 3);
                item.inProgress = true;
                folder.children = [item];
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('folder can be dropped if target is figshare addon root with type project', () => {
                folder = getItem('folder', 0);
                folder.data.provider = 'figshare';
                folder.data.isAddonRoot = true;
                folder.data.rootFolderType = 'project';
                item = getItem('folder', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'move');
            });

            it('folder cannot be dropped if target is figshare addon root with type fileset', () => {
                folder = getItem('folder', 2);
                folder.data.provider = 'figshare';
                folder.data.isAddonRoot = false;
                item = getItem('folder', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });

            it('folder cannot be dropped if target is figshare non-root fileset', () => {
                folder = getItem('folder', 0);
                folder.data.provider = 'figshare';
                folder.data.isAddonRoot = true;
                folder.data.rootFolderType = 'fileset';
                item = getItem('folder', 3);
                assert.equal(Fangorn.getCopyMode(folder, [item]), 'forbidden');
            });
        });

        describe('isInvalidDropFolder', () => {
            it('can be dropped if valid', () => {
                assert.equal(Fangorn.isInvalidDropFolder(getItem('folder')), false);
            });

            it('cannot be dropped if target parentID is root', () => {
                folder = getItem('folder');
                folder.parentID = 0;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('cannot be dropped into if target inProgress is true', () => {
                folder = getItem('folder');
                folder.inProgress = true;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('cannot be dropped if target kind is undefined', () => {
                assert.equal(Fangorn.isInvalidDropFolder(getItem()), true);
            });

            it('cannot be dropped if target kind is file', () => {
                assert.equal(Fangorn.isInvalidDropFolder(getItem('file')), true);
            });

            it('cannot be dropped if no edit permission for target', () => {
                folder = getItem('folder');
                folder.data.permissions.edit = false;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('cannot be dropped if target has no provider', () => {
                folder = getItem('folder');
                folder.data.provider = null;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('cannot be dropped if target has an associated status', () => {
                folder = getItem('folder');
                folder.data.status = true;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('cannot be dropped if target provider is dataverse', () => {
                folder = getItem('folder');
                folder.data.provider = 'dataverse';
                folder.data.dataverseIsPublished = true;
                assert.equal(Fangorn.isInvalidDropFolder(folder), true);
            });

            it('can be dropped if provider dataverse and dataverse is not published', () => {
                folder = getItem('folder');
                folder.data.provider = 'dataverse';
                folder.data.dataverseIsPublished = false;
                assert.equal(Fangorn.isInvalidDropFolder(folder), false);
            });

        });

        describe('isInvalidDropItem', () => {
            it('can be dropped if valid', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), false);
            });

            it('cannot be dropped if item has a nodeType', () => {
                folder = getItem('folder', 2);
                item = getItem('folder', 3);
                item.data.nodeType = 'project';
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('cannot be dropped if item is an addonRoot', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.isAddonRoot = true;
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('cannot be dropped if item and target are the same', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 2);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('cannot be dropped if the target is the current parent', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.parentID = 2;
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('can be dropped if item provider is dataverse and item is not published', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'dataverse';
                item.data.extra.hasPublishedVersion = false;
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), false);
            });

            it('cannot be dropped if item provider is dataverse and item is published', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'dataverse';
                item.data.extra.hasPublishedVersion = true;
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('cannot be dropped if folder provider dataverse and item is a folder', () => {
                folder = getItem('folder', 2);
                folder.data.provider = 'dataverse';
                item = getItem('folder', 3);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('can be dropped if provider dataverse and item is not a folder', () => {
                folder = getItem('folder', 2);
                folder.data.provider = 'dataverse';
                item = getItem('file', 3);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), false);
            });

            it('cannot be dropped if item inProgress is true', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.inProgress = true;
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), true);
            });

            it('can be dropped if folder and allowed to be folder', () => {
                folder = getItem('folder', 2);
                item = getItem('folder', 3);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, false), false);
            });

            it('cannot be dropped if folder and not allowed to be folder', () => {
                folder = getItem('folder', 2);
                item = getItem('folder', 3);
                assert.equal(Fangorn.isInvalidDropItem(folder, item, true, false), true);
            });

            it('can be dropped if mustBeIntra is true and same provider', () => {
                folder = getItem('folder', 2);
                folder.data.provider = 'github';
                item = getItem('file', 3);
                item.data.provider = 'github';
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, true), false);
            });

            it('cannot be dropped if mustBeIntra is true and not same provider', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'github';
                assert.equal(Fangorn.isInvalidDropItem(folder, item, false, true), true);
            });
        });

        describe('allowedToMove', () => {
            it('can move if valid', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                assert.equal(Fangorn.allowedToMove(folder, item, false), true);
            });

            it('cannot move if edit permisisons false', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.permissions.edit = false;
                assert.equal(Fangorn.allowedToMove(folder, item, false), false);
            });

            it('cannot move if mustBeIntra is true and not same provider', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'google';
                assert.equal(Fangorn.allowedToMove(folder, item, true), false);
            });

            it('cannot move if mustBeIntra is true and not same node', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                folder.data.nodeId = 'abcde';
                item.data.nodeId = 'ebcde';
                assert.equal(Fangorn.allowedToMove(folder, item, true), false);
            });

            it('can move if mustBeIntra is true and same provider and same node', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                folder.data.nodeId = 'abcde';
                item.data.nodeId = 'abcde';
                assert.equal(Fangorn.allowedToMove(folder, item, true), true);
            });

            it('cannot move item from figshare if it is public', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'figshare';
                item.data.extra = {'status': 'public'};
                assert.equal(Fangorn.allowedToMove(folder, item, false), false);
            });

            it('can move item from figshare if it is private', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.data.provider = 'figshare';
                item.data.extra = {'status': 'draft'};
                assert.equal(Fangorn.allowedToMove(folder, item, false), true);
            });
        });

        describe('checkConflicts', () => {
            it('returns conflict if moved file (name) already exist in folder', () => {
                var folder = getItem('folder', 2);
                var item = getItem('file', 5, 'exp.csv');
                var itemDropped = getItem('file', 6, 'exp.csv');
                folder.children = [item];
                assert.deepEqual(Fangorn.checkConflicts([itemDropped], folder).conflicts, [itemDropped]);
                assert.equal(Fangorn.checkConflicts([itemDropped], folder).ready.length, 0);
            });

            it('returns no conflicts if no file(s) of same name exist in folder', () => {
                var folder = getItem('folder', 2);
                var item = getItem('file', 3, 'exp.csv');
                var item1 = getItem('file', 5, 'exp1.csv');
                var item2 = getItem('file', 6, 'exp2.csv');
                var movedItems = [item1, item2];
                folder.children = [item];
                assert.equal(Fangorn.checkConflicts(movedItems, folder).conflicts.length, 0);
                assert.equal(Fangorn.checkConflicts(movedItems, folder).ready.length, movedItems.length);
                assert.deepEqual(Fangorn.checkConflicts(movedItems, folder).ready, movedItems);

            });

            it('returns no conflicts if folder with similar files is dropped', () => {
                var folder = getItem('folder', 2);
                var item3 = getItem('file', 3, 'pluto.csv');
                var item5 = getItem('file', 5, 'mars.csv');
                folder.children = [item3, item5];

                var folder2 = getItem('folder', 6);
                var item7 = getItem('file', 7, 'pluto.csv');
                var item8 = getItem('file', 8, 'mars.csv');
                folder2.children = [item7, item8];

                var movedFolder = folder2;
                assert.equal(Fangorn.checkConflicts([movedFolder], folder).conflicts.length, 0);
                assert.deepEqual(Fangorn.checkConflicts([movedFolder], folder).ready, [movedFolder]);
            });

        });

        describe('getAllChildren', () => {
            it('returns no children when there are no children', () => {
                folder = getItem('folder', 2);
                assert.equal(Fangorn.getAllChildren(item).length, 0);
            });

            it('returns one child when there is only one child', () => {
                folder = getItem('folder', 2);
                item = getItem('file', 3);
                item.children = [folder];
                assert.equal(Fangorn.getAllChildren(item).length, 1);
            });

            it('returns two children when child has a child', () => {
                folder = getItem('folder', 2);
                var folder2 = getItem('folder', 3);
                item = getItem('file', 4);
                folder2.children = [item];
                folder.children = [folder2];
                assert.equal(Fangorn.getAllChildren(folder).length, 2);
            });
        });

        describe('showDeleteMultiple', () => {
            it('does not show multi delete if no edit permissions', () => {
                folder = getItem('folder', 2);
                folder.data.permissions.edit = false;
                item = getItem('file', 3);
                item.data.permissions.edit = false;
                assert.equal(Fangorn.showDeleteMultiple([folder, item]), false);
            });

            it('does show multi delete if edit permissions for at least one selected', () => {
                folder = getItem('folder', 2);
                folder.data.permissions.edit = false;
                item = getItem('file', 3);
                item.data.permissions.edit = true;
                assert.equal(Fangorn.showDeleteMultiple([folder, item]), true);
            });

            it('does show multi delete if edit permissions for all selected', () => {
                folder = getItem('folder', 2);
                folder.data.permissions.edit = true;
                item = getItem('file', 3);
                item.data.permissions.edit = true;
                assert.equal(Fangorn.showDeleteMultiple([folder, item]), true);
            });
        });

        describe('shouldSkipSizeCheck', () => {
            it('returns true for a move where source and destination provider match', () => {
                var operation = {status: 'move'};
                assert.equal(Fangorn.shouldSkipSizeCheck(operation, 'osfstorage', 'osfstorage'), true);
            });

            it('returns false for a move where source and destination provider differ', () => {
                var operation = {status: 'move'};
                assert.equal(Fangorn.shouldSkipSizeCheck(operation, 'osfstorage', 's3'), false);
            });

            it('returns false for a copy even when provider matches', () => {
                var operation = {status: 'copy'};
                assert.equal(Fangorn.shouldSkipSizeCheck(operation, 'osfstorage', 'osfstorage'), false);
            });

            it('returns false for a copy where provider also differs', () => {
                var operation = {status: 'copy'};
                assert.equal(Fangorn.shouldSkipSizeCheck(operation, 'osfstorage', 's3'), false);
            });
        });

        describe('isSameUserQuota', () => {
            it('returns true when user_guid and storage_type both match', () => {
                var src = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                var dest = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, dest), true);
            });

            it('returns false when user_guid differs', () => {
                var src = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                var dest = {user_guid: 'xyz', storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, dest), false);
            });

            it('returns false when storage_type differs', () => {
                var src = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                var dest = {user_guid: 'abc', storage_type: 'CUSTOM_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, dest), false);
            });

            it('returns false when user_guid is undefined on either side', () => {
                var src = {storage_type: 'NII_STORAGE'};
                var dest = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, dest), false);
            });

            it('returns false when user_guid is null on both sides', () => {
                var src = {user_guid: null, storage_type: 'NII_STORAGE'};
                var dest = {user_guid: null, storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, dest), false);
            });

            it('returns false when srcQuota is falsy', () => {
                var dest = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(null, dest), false);
            });

            it('returns false when destQuota is falsy', () => {
                var src = {user_guid: 'abc', storage_type: 'NII_STORAGE'};
                assert.equal(Fangorn.isSameUserQuota(src, null), false);
            });
        });

        describe('quotaCheckExceeds', () => {
            it('returns true when used + totalSize exceeds max', () => {
                var destQuota = {used: 800, max: 1000};
                assert.equal(Fangorn.quotaCheckExceeds(destQuota, 300, 0), true);
            });

            it('returns false when used + totalSize stays within max', () => {
                var destQuota = {used: 800, max: 1000};
                assert.equal(Fangorn.quotaCheckExceeds(destQuota, 100, 0), false);
            });

            it('returns false when used + totalSize lands exactly on max', () => {
                var destQuota = {used: 800, max: 1000};
                assert.equal(Fangorn.quotaCheckExceeds(destQuota, 200, 0), false);
            });

            it('subtracts replacedSize before comparing to max', () => {
                var destQuota = {used: 800, max: 1000};
                // Without replacedSize this would exceed (800 + 300 > 1000),
                // but the 150 freed by the overwrite brings it back within max.
                assert.equal(Fangorn.quotaCheckExceeds(destQuota, 300, 150), false);
            });

            it('treats a missing replacedSize as 0', () => {
                var destQuota = {used: 800, max: 1000};
                assert.equal(Fangorn.quotaCheckExceeds(destQuota, 300), true);
            });
        });

        describe('getReplacedSize', () => {
            // Fixture builder for treebeard-like nodes: getReplacedSize/hasUnloadedFolder
            // read top-level `kind`/`load`, unlike the `getItem` helper above which only
            // sets `data.kind`.
            var makeNode = function(kind, name, opts) {
                opts = opts || {};
                return {
                    kind: kind,
                    data: {
                        name: name,
                        size: opts.size
                    },
                    children: opts.children || [],
                    load: opts.load !== undefined ? opts.load : true
                };
            };

            it('returns 0 when conflict is not replace', () => {
                var to = {children: []};
                var from = makeNode('file', 'a.txt', {size: 10});
                assert.equal(Fangorn.getReplacedSize(to, from, 'keep'), 0);
            });

            it('returns 0 when no existing item matches name and kind', () => {
                var to = {children: [makeNode('file', 'other.txt', {size: 10})]};
                var from = makeNode('file', 'a.txt', {size: 10});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), 0);
            });

            it('does not match when name is the same but kind differs', () => {
                var to = {children: [makeNode('folder', 'a', {})]};
                var from = makeNode('file', 'a', {size: 10});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), 0);
            });

            it('returns the existing file size when replacing a file', () => {
                var existing = makeNode('file', 'a.txt', {size: 500});
                var to = {children: [existing]};
                var from = makeNode('file', 'a.txt', {size: 10});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), 500);
            });

            it('returns 0 when the existing file has no size', () => {
                var existing = makeNode('file', 'a.txt', {});
                var to = {children: [existing]};
                var from = makeNode('file', 'a.txt', {size: 10});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), 0);
            });

            it('sums the sizes of all files in a fully loaded existing folder', () => {
                var child1 = makeNode('file', 'x.txt', {size: 100});
                var child2 = makeNode('file', 'y.txt', {size: 200});
                var subfolder = makeNode('folder', 'sub', {children: [child1, child2], load: true});
                var existing = makeNode('folder', 'a', {children: [subfolder], load: true});
                var to = {children: [existing]};
                var from = makeNode('folder', 'a', {});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), 300);
            });

            it('returns null when the existing folder itself has not been lazy-loaded', () => {
                var existing = makeNode('folder', 'a', {load: false});
                var to = {children: [existing]};
                var from = makeNode('folder', 'a', {});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), null);
            });

            it('returns null when a nested subfolder has not been lazy-loaded', () => {
                var unloadedSub = makeNode('folder', 'sub', {load: false});
                var existing = makeNode('folder', 'a', {children: [unloadedSub], load: true});
                var to = {children: [existing]};
                var from = makeNode('folder', 'a', {});
                assert.equal(Fangorn.getReplacedSize(to, from, 'replace'), null);
            });
        });
    });

    describe('doItemOp', () => {
        var ajaxStub;
        var growlStub;
        var ravenStub;

        beforeEach(() => {
            growlStub = sinon.stub($osf, 'growl');
            ravenStub = sinon.stub(Raven, 'captureMessage');
        });

        afterEach(() => {
            if (ajaxStub) { ajaxStub.restore(); }
            growlStub.restore();
            ravenStub.restore();
        });

        // Fixture builder for a fake Treebeard node with just enough of the
        // real API (move/parent/notify/add/removeSelf) for doItemOp to run.
        function makeParent() {
            return {
                data: {
                    nodeUrl: 'https://osf.io/proj1/',
                    nodeApiUrl: 'https://osf.io/proj1/api/',
                    nodeId: 'proj1',
                    permissions: {edit: true},
                    provider: 'osfstorage'
                },
                sortChildren: sinon.stub()
            };
        }

        function makeItem(kind, data, id, parentID) {
            return {
                kind: kind,
                data: $.extend({provider: 'osfstorage'}, data),
                children: [],
                id: id,
                parentID: parentID,
                inProgress: false,
                notify: {update: sinon.stub()},
                move: sinon.stub(),
                add: sinon.stub(),
                removeSelf: sinon.stub(),
                parent: sinon.stub().returns(makeParent())
            };
        }

        // Fixture builder for a fake Treebeard.controller (`this` inside doItemOp).
        function makeTb() {
            var tb = {
                modal: {dismiss: sinon.stub(), update: sinon.stub()},
                pendingFileOps: [],
                pendingReadyFiles: [],
                moveStates: [],
                uploadStates: [],
                syncFileMoveCache: {osfstorage: {conflicts: [], ready: []}, s3compat: {conflicts: [], ready: []}},
                clearMultiselect: sinon.stub(),
                redraw: sinon.stub(),
                select: sinon.stub().returns({hide: sinon.stub(), css: sinon.stub()}),
                options: {
                    lazyLoadPreprocess: function(resp) { return {data: resp}; }
                }
            };
            tb.createItem = sinon.stub().callsFake(function(data) {
                return makeItem(data.kind, data);
            });
            tb.buildTree = sinon.stub().callsFake(function(data) {
                return makeItem(data.kind, data);
            });
            return tb;
        }

        // A minimal fake jQuery Deferred supporting the .done()/.fail()/.always()
        // chain doItemOp attaches to the final POST call.
        function fakeDeferred(config) {
            var obj = {
                done: function(cb) {
                    if (config.status === 'done') { cb.apply(null, config.args || []); }
                    return obj;
                },
                fail: function(cb) {
                    if (config.status === 'fail') { cb.apply(null, config.args || []); }
                    return obj;
                },
                always: function(cb) { cb(); return obj; }
            };
            return obj;
        }

        function stubAjax(responder) {
            ajaxStub = sinon.stub($, 'ajax').callsFake(responder);
        }

        function growlCallWithType(type) {
            return growlStub.getCalls().some(function(call) { return call.args[2] === type; });
        }

        it('returns without calling the API when dropped back onto its own parent', () => {
            var tb = makeTb();
            var to = makeItem('folder', {nodeApiUrl: 'https://osf.io/to/'}, 5, undefined);
            var from = makeItem('file', {name: 'a.txt', size: 10}, 3, 5);
            ajaxStub = sinon.stub($, 'ajax');
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(ajaxStub.called, false);
        });

        it('rejects the move without calling the API when a file exceeds the destination max size', () => {
            var tb = makeTb();
            // Different providers: shouldSkipSizeCheck only shortcuts a same-provider move,
            // so this keeps the client-side oversized check from being bypassed.
            var to = makeItem('folder', {provider: 's3compat', nodeApiUrl: 'https://osf.io/to/', accept: {maxSize: 1}}, 5, 1);
            var from = makeItem('file', {name: 'big.txt', size: 5000000}, 3, 1);
            ajaxStub = sinon.stub($, 'ajax');
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(ajaxStub.called, false);
            assert.equal(growlStub.called, true);
            assert.equal(from.inProgress, false);
        });

        it('rejects the copy without calling the API when it would exceed quota', () => {
            var tb = makeTb();
            var to = makeItem('folder', {nodeApiUrl: 'https://osf.io/to/'}, 5, 1);
            var from = makeItem('file', {name: 'a.txt', size: 100}, 3, 1);
            stubAjax(function(opts) {
                if (opts.method === 'GET') {
                    return {responseJSON: {used: 950, max: 1000, user_guid: 'u1', storage_type: 'NII_STORAGE'}};
                }
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.COPY, to, from, undefined, undefined);
            assert.equal(ajaxStub.callCount, 1);
            assert.equal(from.notify.update.called, true);
            assert.equal(from.inProgress, false);
        });

        it('skips the quota check and proceeds when source and destination share the same UserQuota record', () => {
            var tb = makeTb();
            var to = makeItem('folder', {nodeApiUrl: 'https://osf.io/to/', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {nodeApiUrl: 'https://osf.io/from/', name: 'a.txt', size: 999999, path: '/a.txt'}, 3, 1);
            var sameQuota = {used: 10, max: 1000000000, user_guid: 'u1', storage_type: 'NII_STORAGE'};
            stubAjax(function(opts) {
                if (opts.method === 'GET') {
                    return {responseJSON: sameQuota};
                }
                if (opts.type === 'POST') {
                    return fakeDeferred({status: 'done', args: [
                        {name: 'a.txt', provider: 'osfstorage', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/to/'},
                        'success',
                        {status: 200}
                    ]});
                }
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            // dest quota GET + src quota GET (different node) + the real POST
            assert.equal(ajaxStub.callCount, 3);
            assert.equal(tb.uploadStates.length, 1);
            assert.equal(tb.uploadStates[0].success, true);
        });

        it('shows a quota usage alert on success once the destination crosses the warning threshold', () => {
            var tb = makeTb();
            var to = makeItem('folder', {nodeApiUrl: 'https://osf.io/to/', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {name: 'a.txt', size: 150}, 3, 1);
            stubAjax(function(opts) {
                if (opts.method === 'GET') {
                    // used(800) + totalSize(150) = 950 <= max(1000) -> not rejected,
                    // but 950 > max * threshold(0.9) = 900 -> alert should fire.
                    return {responseJSON: {used: 800, max: 1000, user_guid: 'u1', storage_type: 'NII_STORAGE'}};
                }
                if (opts.type === 'POST') {
                    return fakeDeferred({status: 'done', args: [
                        {name: 'a.txt', provider: 'osfstorage', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/to/'},
                        'success',
                        {status: 200}
                    ]});
                }
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.COPY, to, from, undefined, undefined);
            assert.equal(growlCallWithType('warning'), true);
        });

        it('creates a new item via tb.createItem for a COPY and posts a copy action', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', nodeApiUrl: 'https://osf.io/to/', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            var postedData;
            stubAjax(function(opts) {
                postedData = JSON.parse(opts.data);
                return fakeDeferred({status: 'done', args: [
                    {name: 'a.txt', provider: 's3compat', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/to/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.COPY, to, from, undefined, undefined);
            assert.equal(tb.createItem.called, true);
            assert.equal(postedData.action, 'copy');
        });

        it('posts a rename action for a RENAME operation', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'old.txt'}, 3, 9);
            var postedData;
            stubAjax(function(opts) {
                postedData = JSON.parse(opts.data);
                return fakeDeferred({status: 'done', args: [
                    {name: 'new.txt', provider: 's3compat', path: '/new.txt', kind: 'file', nodeUrl: 'https://osf.io/proj1/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.RENAME, to, from, 'new.txt', undefined);
            assert.equal(postedData.action, 'rename');
            assert.equal(postedData.rename, 'new.txt');
        });

        it('shows a pending growl and stops when the API responds 202', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'done', args: [{}, 'success', {status: 202}]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(growlCallWithType('info'), true);
            assert.equal(tb.uploadStates.length, 0);
        });

        it('shows an oversized-file growl and records a failure when the API rejects with 413', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [
                    {status: 413, responseJSON: {oversized_files: [{name: 'big.txt', size: 5000000}], max_size: 1000000}},
                    'error'
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(growlStub.called, true);
            assert.equal(tb.uploadStates.length, 1);
            assert.equal(tb.uploadStates[0].success, false);
        });

        it('shows the mapped MESSAGE_MAP text when the API rejects with 406 and a known message_key', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [
                    {status: 406, responseJSON: {message: 'raw message', message_key: 'quota_exceeded'}},
                    'error'
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(growlStub.called, true);
            assert.equal(tb.uploadStates[0].success, false);
        });

        it('reports to Raven and shows a fallback message when the API fails with a generic 500', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [{status: 500}, 'error']});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(ravenStub.called, true);
            assert.equal(growlStub.called, true);
        });

        // The cases below close the gaps found in the coverage report
        // (RDM-osf.io/coverage/html/js/fangorn.js.html) for _findOversizedFiles
        // and doItemOp. See investigation/2026-09-03-fangorn-coverage-findoversizedfiles-doitemop.md.

        it('rejects a folder move and reports oversized files found inside it', () => {
            var tb = makeTb();
            // Different providers: shouldSkipSizeCheck only shortcuts a same-provider move.
            var to = makeItem('folder', {provider: 's3compat', nodeApiUrl: 'https://osf.io/to/', accept: {maxSize: 1}}, 5, 1);
            var from = makeItem('folder', {name: 'myFolder'}, 3, 1);
            var smallChild = makeItem('file', {name: 'small.txt', size: 100}, 10, 3);
            var bigChild = makeItem('file', {name: 'big.txt', size: 5000000}, 11, 3);
            from.children = [smallChild, bigChild];
            ajaxStub = sinon.stub($, 'ajax');
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(ajaxStub.called, false);
            assert.equal(growlStub.called, true);
            assert.equal(from.inProgress, false);
        });

        it('sums child file sizes when moving a folder and rejects if quota would be exceeded', () => {
            var tb = makeTb();
            var to = makeItem('folder', {nodeApiUrl: 'https://osf.io/to/'}, 5, 1);
            var from = makeItem('folder', {name: 'myFolder'}, 3, 1);
            var child = makeItem('file', {name: 'a.txt', size: 200}, 10, 3);
            from.children = [child];
            stubAjax(function(opts) {
                if (opts.method === 'GET') {
                    return {responseJSON: {used: 900, max: 1000, user_guid: 'u1', storage_type: 'NII_STORAGE'}};
                }
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.COPY, to, from, undefined, undefined);
            assert.equal(ajaxStub.callCount, 1);
            assert.equal(from.notify.update.called, true);
            assert.equal(from.inProgress, false);
        });

        it('shows a "conflicts left to resolve" modal when the sync queue has pending conflicts', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            tb.syncFileMoveCache.s3compat = {conflicts: [{item: from, folder: to}], ready: []};
            stubAjax(function() {
                return fakeDeferred({status: 'done', args: [
                    {name: 'a.txt', provider: 's3compat', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/proj1/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(tb.modal.update.called, true);
        });

        it('preserves the branch and checks the sync-ready queue when moving a github item', () => {
            var tb = makeTb();
            // github isn't in the default syncFileMoveCache fixture; add it so the
            // notRenameOp conflicts-check doesn't throw on an undefined entry.
            tb.syncFileMoveCache.github = {conflicts: [], ready: []};
            var to = makeItem('folder', {provider: 'github', path: '/'}, 5, 1);
            var from = makeItem('file', {provider: 'github', name: 'a.txt', branch: 'main'}, 3, 1);
            var postedData;
            stubAjax(function(opts) {
                postedData = JSON.parse(opts.data);
                return fakeDeferred({status: 'done', args: [
                    {name: 'a.txt', provider: 'github', path: '/a.txt', kind: 'file', nodeUrl: 'https://osf.io/proj1/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(postedData.branch, 'main');
        });

        it('removes the existing item at destination when the server responds 200 with a name conflict', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', nodeApiUrl: 'https://osf.io/to/', path: '/dest/'}, 5, 1);
            var existingChild = makeItem('file', {name: 'a.txt', provider: 's3compat'}, 99, 5);
            to.children = [existingChild];
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'done', args: [
                    {name: 'a.txt', provider: 's3compat', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/to/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(existingChild.removeSelf.called, true);
        });

        it('rebuilds the child subtree when the moved item is a folder with children in the response', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', nodeApiUrl: 'https://osf.io/to/', path: '/dest/'}, 5, 1);
            var from = makeItem('folder', {provider: 's3compat', name: 'myFolder'}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'done', args: [
                    {
                        name: 'myFolder', provider: 's3compat', path: '/dest/myFolder/', kind: 'folder',
                        nodeUrl: 'https://osf.io/to/',
                        children: [{name: 'child.txt', kind: 'file', provider: 's3compat'}]
                    },
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.equal(tb.buildTree.called, true);
            assert.equal(from.add.called, true);
            assert.equal(from.open, true);
            assert.equal(from.load, true);
        });

        it('removes the newly created item when a COPY operation fails', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [{status: 500}, 'error']});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.COPY, to, from, undefined, undefined);
            assert.equal(tb.createItem.called, true);
            var createdItem = tb.createItem.returnValues[0];
            assert.equal(createdItem.removeSelf.called, true);
        });

        it('shows the responseJSON message for a non-413/406/500/503 failure', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [
                    {status: 400, responseJSON: {message: 'custom failure message'}},
                    'error'
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            var calledWithMessage = growlStub.getCalls().some(function(call) { return call.args[1] === 'custom failure message'; });
            assert.equal(calledWithMessage, true);
        });

        it('uses textStatus as the error message on a 503 response', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            stubAjax(function() {
                return fakeDeferred({status: 'fail', args: [{status: 503}, 'Service Unavailable']});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            var calledWithMessage = growlStub.getCalls().some(function(call) { return call.args[1] === 'Service Unavailable'; });
            assert.equal(calledWithMessage, true);
        });

        it('removes the settled item from pendingReadyFiles once the operation completes', () => {
            var tb = makeTb();
            var to = makeItem('folder', {provider: 's3compat', path: '/dest/'}, 5, 1);
            var from = makeItem('file', {provider: 's3compat', name: 'a.txt', size: 10}, 3, 1);
            var other = makeItem('file', {name: 'other.txt'}, 77, 1);
            tb.pendingReadyFiles = [from, other];
            stubAjax(function() {
                return fakeDeferred({status: 'done', args: [
                    {name: 'a.txt', provider: 's3compat', path: '/dest/a.txt', kind: 'file', nodeUrl: 'https://osf.io/proj1/'},
                    'success',
                    {status: 200}
                ]});
            });
            Fangorn.doItemOp.call(tb, Fangorn.OPERATIONS.MOVE, to, from, undefined, undefined);
            assert.deepEqual(tb.pendingReadyFiles, [other]);
        });
    });
});
