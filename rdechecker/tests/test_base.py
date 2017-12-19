# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from os import path as osp

from .. import __main__ as m

mydir = osp.dirname(__file__)


class TBase(unittest.TestCase):

    def test_yaml_file(self):
        m.process_files(osp.join(mydir, 'test.csv'))
