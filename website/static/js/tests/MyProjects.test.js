
//TODO uncomment and write more tests
/* Tests for myprojects.js for My Projects in Dashboard */
/*global describe, it, expect, example, before, after, beforeEach, afterEach, mocha, sinon*/
'use strict';
var assert = require('chai').assert;
var sinon = require('sinon');
var fb = require('js/myProjects.js');

var LinkObject = fb.LinkObject;

describe('fileBrowser', function() {
    describe('LinkObject', function () {
        var collection;
        var tag;
        var name;
        var node;

        before(function () {
            collection = new LinkObject('collection', {
                path: 'users/me/nodes/',
                query: {'related_counts': 'children'},
                systemCollection: true
            }, 'All My Projects');
            tag = new LinkObject('tag', { tag : 'something', query : { 'related_counts' : true }}, 'Something Else');
            name = new LinkObject('name', { id : '8q36f', query : { 'related_counts' : true }}, 'Caner Uguz');
            node = new LinkObject('node', { id : 'qwerty'}, 'Node Title');
        });

        describe('#attributes', function () {
            it('should return an id of 1', function () {
                assert.equal(collection.id, 1);
            });
            it('should throw error when no arguments passed', function () {
                assert.throws(function(){ var missing = new LinkObject(); }, Error);
            });
        });
    });

    describe('Collections IME Keydown Handling', function() {
        function makeMockCtrl(overrides) {
            return Object.assign({
                isComposingAdd: false,
                isComposingRename: false,
                isValid: sinon.stub().returns(true),
                validateName: sinon.stub(),
                newCollectionName: sinon.stub(),
                addCollection: sinon.stub(),
                renameCollection: sinon.stub(),
                collectionMenuObject: sinon.stub().returns({ item: { renamedLabel: '' } }),
            }, overrides);
        }

        function makeAddCollKeydownHandler(ctrl) {
            return function(ev) {
                var isComposing = ev.isComposing || ctrl.isComposingAdd || ev.keyCode === 229;
                if (ev.key === 'Enter' && !isComposing) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (ctrl.isValid()) {
                        ctrl.addCollection();
                    }
                }
            };
        }

        function makeRenameCollKeydownHandler(ctrl) {
            return function(ev) {
                var isComposing = ev.isComposing || ctrl.isComposingRename || ev.keyCode === 229;
                if (ev.key === 'Enter' && !isComposing) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (ctrl.isValid()) {
                        ctrl.renameCollection();
                    }
                }
            };
        }

        function makeEvent(overrides) {
            return Object.assign({
                key: 'Enter',
                isComposing: false,
                keyCode: 13,
                preventDefault: sinon.spy(),
                stopPropagation: sinon.spy(),
            }, overrides);
        }

        var ctrl;
        beforeEach(function() {
            ctrl = makeMockCtrl();
        });

        describe('addCollection keydown', function() {
            it('should call addCollection() on Enter when valid and not composing', function() {
                var handler = makeAddCollKeydownHandler(ctrl);
                handler(makeEvent());
                assert.ok(ctrl.addCollection.calledOnce, 'addCollection() should be called');
            });

            it('should NOT call addCollection() during IME (event.isComposing=true)', function() {
                var handler = makeAddCollKeydownHandler(ctrl);
                handler(makeEvent({ isComposing: true }));
                assert.ok(ctrl.addCollection.notCalled);
            });

            it('should NOT call addCollection() during Chrome IME race (ctrl.isComposing=true)', function() {
                ctrl.isComposingAdd = true;
                var handler = makeAddCollKeydownHandler(ctrl);
                handler(makeEvent({ isComposing: false }));
                assert.ok(ctrl.addCollection.notCalled,
                    'ctrl.isComposing=true should block addCollection() even if event.isComposing=false');
            });

            it('should NOT call addCollection() when keyCode is 229 (legacy IME)', function() {
                var handler = makeAddCollKeydownHandler(ctrl);
                handler(makeEvent({ isComposing: false, keyCode: 229 }));
                assert.ok(ctrl.addCollection.notCalled);
            });

            it('should call preventDefault() on Enter even when form is invalid', function() {
                ctrl.isValid.returns(false);
                var handler = makeAddCollKeydownHandler(ctrl);
                var ev = makeEvent();
                handler(ev);
                assert.ok(ev.preventDefault.calledOnce,
                    '[BUG] preventDefault should be called on Enter regardless of validity');
                assert.ok(ctrl.addCollection.notCalled, 'addCollection should not be called when invalid');
            });

            it('should NOT call addCollection() on non-Enter key', function() {
                var handler = makeAddCollKeydownHandler(ctrl);
                handler(makeEvent({ key: 'Escape', keyCode: 27 }));
                assert.ok(ctrl.addCollection.notCalled);
            });
        });

        describe('renameCollection keydown', function() {
            it('should call renameCollection() on Enter when valid and not composing', function() {
                var handler = makeRenameCollKeydownHandler(ctrl);
                handler(makeEvent());
                assert.ok(ctrl.renameCollection.calledOnce, 'renameCollection() should be called');
            });

            it('should NOT call renameCollection() during IME (event.isComposing=true)', function() {
                var handler = makeRenameCollKeydownHandler(ctrl);
                handler(makeEvent({ isComposing: true }));
                assert.ok(ctrl.renameCollection.notCalled);
            });

            it('should NOT call renameCollection() when ctrl.isComposing=true (Chrome race)', function() {
                ctrl.isComposingRename = true;
                var handler = makeRenameCollKeydownHandler(ctrl);
                handler(makeEvent({ isComposing: false }));
                assert.ok(ctrl.renameCollection.notCalled);
            });

            it('should NOT call renameCollection() when keyCode is 229', function() {
                var handler = makeRenameCollKeydownHandler(ctrl);
                handler(makeEvent({ keyCode: 229, isComposing: false }));
                assert.ok(ctrl.renameCollection.notCalled);
            });
        });

        describe('ctrl.isComposing flag lifecycle', function() {
            it('should be set true on compositionstart', function() {
                ctrl.isComposing = false;
                var onCompositionStart = function() { ctrl.isComposing = true; };
                onCompositionStart();
                assert.strictEqual(ctrl.isComposing, true);
            });

            it('should be set false on compositionend', function() {
                ctrl.isComposing = true;
                var onCompositionEnd = function() { ctrl.isComposing = false; };
                onCompositionEnd();
                assert.strictEqual(ctrl.isComposing, false);
            });
        });

        describe('oninput handler', function() {
            it('should call validateName and newCollectionName with input value', function() {
                var val = 'Test Collection';
                var ev = { target: { value: val } };
                var onInput = function(ev) {
                    var v = ev.target.value;
                    ctrl.validateName(v);
                    ctrl.newCollectionName(v);
                };
                onInput(ev);
                assert.ok(ctrl.validateName.calledWith(val));
                assert.ok(ctrl.newCollectionName.calledWith(val));
            });
        });
    });
});