# -*- coding: utf-8 -*-

import pytest

from addons.workflow.token import MAX_TOKEN_NAME_LENGTH, build_token_name


class TestBuildTokenName:
    def test_no_label(self):
        name = build_token_name('executor')
        assert name == 'Workflow delegation: executor'

    def test_short_label(self):
        name = build_token_name('executor', 'test on proj')
        assert name == 'Workflow delegation: executor (test on proj)'
        assert len(name) <= MAX_TOKEN_NAME_LENGTH

    def test_exact_boundary(self):
        # 'Workflow delegation: executor' = 29 chars
        # suffix = ' (' + label + ')' = len(label) + 3
        # total = 32 + len(label) = 100 => len(label) = 68
        label = 'x' * 68
        name = build_token_name('executor', label)
        assert len(name) == MAX_TOKEN_NAME_LENGTH
        assert '...' not in name

    def test_one_over_truncates(self):
        label = 'x' * 69
        name = build_token_name('executor', label)
        assert len(name) == MAX_TOKEN_NAME_LENGTH
        assert name.endswith('...)')

    def test_very_long_label(self):
        label = 'x' * 300
        name = build_token_name('executor', label)
        assert len(name) == MAX_TOKEN_NAME_LENGTH
        assert name.endswith('...)')

    def test_japanese_label(self):
        label = '論文・根拠データ公開申請(ファイル選択) on ' + 'あ' * 100
        name = build_token_name('executor', label)
        assert len(name) <= MAX_TOKEN_NAME_LENGTH
        assert name.startswith('Workflow delegation: executor (')

    def test_all_roles(self):
        for role in ('creator', 'manager', 'executor'):
            name = build_token_name(role, 'a' * 200)
            assert len(name) <= MAX_TOKEN_NAME_LENGTH
