# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from os import path as osp

from .. import RdeChecker, _match_section_break
import ddt

mydir = osp.dirname(__file__)


@ddt.ddt
class TBase(unittest.TestCase):

    @ddt.data(
        ('', 3, 2, False),
        ('\n', 3, 2, False),
        ('\n\n\n', 3, 2, False),

        ('\n\n', 3, 2, True),
        (',,,\n,,,\n', 3, 2, True),

        (',,\n,,,\n', 3, 2, False),
        (',,,\n,,\n', 3, 2, False),
        ('\n,,,\n', 3, 2, False),
        (',,,\n\n', 3, 2, False),
        (',,,\n,,,\n,,,', 3, 2, False),
    )
    def test_section_break_match(self, data):
        got_lines, exp_ncolumns, exp_nlines, exp_result = data
        got_result = _match_section_break(got_lines,
                            exp_ncolumns, ',', exp_nlines)
        assert bool(got_result) is exp_result

    def test_validation(self):
        rde = RdeChecker(['f1:Sample_Data_Exchange_File.csv'])
        rde.process_files()
