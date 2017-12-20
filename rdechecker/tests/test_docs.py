#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import rdechecker
import subprocess
import unittest
from unittest.mock import patch

import os.path as osp


mydir = osp.dirname(__file__)
proj_path = osp.join(mydir, '..', '..')
readme_path = osp.join(proj_path, 'README.rst')


class Doctest(unittest.TestCase):

    def test_README_version_opening(self):
        ver = rdechecker.__version__
        header_len = 20
        mydir = osp.dirname(__file__)
        with open(readme_path) as fd:
            for i, l in enumerate(fd):
                if ver in l:
                    break
                elif i >= header_len:
                    msg = "Version(%s) not found in README %s header-lines!"
                    raise AssertionError(msg % (ver, header_len))

    def test_README_as_PyPi_landing_page(self):
        from docutils import core as dcore

        long_desc = subprocess.check_output(
            'python setup.py --long-description'.split(),
            cwd=proj_path)
        self.assertIsNotNone(long_desc, 'Long_desc is null!')

        with patch('sys.exit'):
            dcore.publish_string(
                long_desc, enable_exit_status=False,
                settings_overrides={  # see `docutils.frontend` for more.
                    'halt_level': 2  # 2=WARN, 1=INFO
                })
