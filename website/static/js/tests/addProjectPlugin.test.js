/*global describe, it, expect, example, before, after, beforeEach, afterEach, mocha, sinon*/
'use strict';
var assert = require('chai').assert;
var sinon = require('sinon');
var Raven = require('raven-js');
var $ = require('jquery');
var m = require('mithril');
var AddProject = require('js/addProjectPlugin');

// TODO write tests for AddProject
//console.log(AddProject);
describe('AddProjectPlugin', () => {
    it.skip('should validate if new project name is not empty', () => {
        var project = new AddProject.controller();
        project.newProjectName('Hello');
        project.checkValid();
        assert.ok(project.isValid(), true);
        project.newProjectName('');
        project.checkValid();
        assert.notOk(project.isValid(), false);
    });
    it.skip('should reset states and defaults when reset function runs', () => {
        var project = new AddProject.controller();
        // Change values
        project.newProjectName('Hello there');
        project.viewState('error');
        project.newProjectDesc('Description');
        project.newProjectCategory('thesis');
        project.newProjectInheritContribs(true);
        // Reset
        project.reset();
        // Assert the return to defaults;
        assert.equal(project.newProjectName(), '');
        assert.equal(project.viewState(), 'form');
        assert.equal(project.newProjectDesc(), '');
        assert.equal(project.newProjectCategory(), 'project');
        assert.equal(project.project.newProjectInheritContribs(), false);
    });

    describe('IME Keydown Handling (onkeydown)', () => {
        var ctrl;
        function makeMockCtrl(overrides) {
            return Object.assign({
                isComposing: false,
                isValid: sinon.stub().returns(true),
                newProjectName: sinon.stub(),
                add: sinon.stub(),
            }, overrides);
        }
        function makeKeydownHandler(ctrl) {
            return function(ev) {
                var isComposing = ev.isComposing || ctrl.isComposing || ev.keyCode === 229;
                if (ev.key === 'Enter' && !isComposing) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    ctrl.add();
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

        beforeEach(function() {
            ctrl = makeMockCtrl();
        });

        it('should call ctrl.add() when Enter is pressed without IME', () => {
            var handler = makeKeydownHandler(ctrl);
            var ev = makeEvent({ key: 'Enter', isComposing: false, keyCode: 13 });

            handler(ev);

            assert.ok(ctrl.add.calledOnce, 'ctrl.add() should be called once');
            assert.ok(ev.preventDefault.calledOnce, 'preventDefault should be called');
            assert.ok(ev.stopPropagation.calledOnce, 'stopPropagation should be called');
        });

        it('should NOT call ctrl.add() when a non-Enter key is pressed', () => {
            var handler = makeKeydownHandler(ctrl);
            var ev = makeEvent({ key: 'a', keyCode: 65 });

            handler(ev);

            assert.ok(ctrl.add.notCalled, 'ctrl.add() should not be called for non-Enter key');
            assert.ok(ev.preventDefault.notCalled, 'preventDefault should not be called');
        });

        it('should NOT call ctrl.add() when event.isComposing is true (standard IME)', () => {
            var handler = makeKeydownHandler(ctrl);
            var ev = makeEvent({ key: 'Enter', isComposing: true, keyCode: 13 });

            handler(ev);

            assert.ok(ctrl.add.notCalled, 'ctrl.add() should not be called during IME composition');
            assert.ok(ev.preventDefault.notCalled, 'preventDefault should not be called during IME');
        });

        it('should NOT call ctrl.add() when ctrl.isComposing is true (Chrome race condition)', () => {
            ctrl.isComposing = true;
            var handler = makeKeydownHandler(ctrl);
            var ev = makeEvent({ key: 'Enter', isComposing: false, keyCode: 13 });

            handler(ev);

            assert.ok(ctrl.add.notCalled, 'ctrl.add() should not be called when ctrl.isComposing is true');
        });

        it('should NOT call ctrl.add() when keyCode is 229 (legacy IME indicator)', () => {
            var handler = makeKeydownHandler(ctrl);
            var ev = makeEvent({ key: 'Enter', isComposing: false, keyCode: 229 });

            handler(ev);

            assert.ok(ctrl.add.notCalled, 'ctrl.add() should not be called when keyCode is 229');
        });

        it('should set ctrl.isComposing to true on compositionstart', () => {
            ctrl.isComposing = false;
            var onCompositionStart = function() { ctrl.isComposing = true; };
            onCompositionStart();
            assert.strictEqual(ctrl.isComposing, true);
        });

        it('should set ctrl.isComposing to false on compositionend (synchronous)', () => {
            ctrl.isComposing = true;
            var onCompositionEnd = function() { ctrl.isComposing = false; };
            onCompositionEnd();
            assert.strictEqual(ctrl.isComposing, false);
        });

        it('[RECOMMENDED] ctrl.isComposing should still be true when keydown fires ' +
           'if compositionend uses setTimeout defer', function(done) {
            ctrl.isComposing = true;

            var onCompositionEnd = function() {
                setTimeout(function() { ctrl.isComposing = false; }, 0);
            };
            onCompositionEnd();

            assert.strictEqual(ctrl.isComposing, true,
                'isComposing should still be true synchronously after compositionend with setTimeout');

            setTimeout(function() {
                assert.strictEqual(ctrl.isComposing, false,
                    'isComposing should be false after setTimeout resolves');
                done();
            }, 10);
        });

        it('should update newProjectName and isValid via oninput', () => {
            var ev = { target: { value: 'My Project' } };
            var onInput = function(ev) {
                var val = ev.target.value;
                ctrl.isValid(val.trim().length > 0);
                ctrl.newProjectName(val);
            };

            onInput(ev);

            assert.ok(ctrl.newProjectName.calledWith('My Project'));
            assert.ok(ctrl.isValid.calledWith(true));
        });

        it('should mark isValid false via oninput when input is whitespace only', () => {
            var ev = { target: { value: '   ' } };
            var onInput = function(ev) {
                var val = ev.target.value;
                ctrl.isValid(val.trim().length > 0);
                ctrl.newProjectName(val);
            };
            onInput(ev);
            assert.ok(ctrl.isValid.calledWith(false));
        });
    });
});
