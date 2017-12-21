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

from rdechecker.callspec import parse_call_spec


mydir = osp.dirname(__file__)


@ddt.ddt
class TCallSpec(unittest.TestCase):

    @ddt.data(
        (['req', [2,3], {1:2}], ('req', [2, 3], {1: 2})),
        (['req', [5,'h']], ('req', [5, 'h'], {})),
        (['req'], ('req', [], {})),

        ({'func': 'rgex'}, ('rgex', [], {})),
        ({'func': 'rgex', 'args': [1]}, ('rgex', [1], {})),
        ({'func': 'rgex', 'args': [1], 'kwds': {1:1}}, ('rgex', [1], {1: 1})),
        ({'func': 'rgex', 'kwds': {1:1}}, ('rgex', [], {1: 1})),

        ('frag' , ('frag', [], {})),

        ## Multi-func
        (['f1', 'f2', ['f3']], [('f1', [], {}),
                                    ('f2', [], {}),
                                    ('f3', [], {})]),
    )
    def test_ok(self, data):
        inp, exp = data
        assert parse_call_spec(inp) == exp
## ERRORS
#parse_rule_spec(['g', 'jdd', 'h'])
#parse_rule_spec(['f1', 'f2', [['f3']]])
