# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import contextlib
import io
from os import path as osp
import unittest

import ddt

import textwrap as tw

from .. import RdeChecker, __main__ as cmain


mydir = osp.dirname(__file__)


@ddt.ddt
class TBase(unittest.TestCase):

    @ddt.data(
        ('', True),
        ('\n', True),
        ('\r\n', True),

        (',', True),
        (',,\n', True),
        (',,,\r\n', True),

        (' ', False),
        ('f\n', False),
        ('\r \n', False),

        (', ', False),
        (', ,\n', False),
        (',f,,\r\n', False),
    )
    def test_section_break_match(self, data):
        got_lines, is_break_line = data
        rde = RdeChecker()
        assert is_break_line == rde._is_section_break_line(got_lines)

    def test_M_version(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            assert 0 == cmain.main(['--version'])
        assert 2 == len(stdout.getvalue().strip().split())

    def test_M_validation(self):
        assert 0 == cmain.main(['f1:rdechecker/tests/Sample_Data_Exchange_File.csv'])

    def test_M_list_fkinds(self):
        exp_out = tw.dedent("""
            - f1: Big file
            - f2: The summary file
        """)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            assert 0 == cmain.main('-l fkinds'.split())
        ## `endswith()` to ignore `!omap` yaml-tag.
        assert stdout.getvalue().strip().endswith(exp_out.strip())
