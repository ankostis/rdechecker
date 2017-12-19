# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Validate Real-Driving-Emissions monitoring files.

USAGE:
  rdecheck [--compress] <file-spec> ...
  rdecheck -l

OPTIONS:
  -l    list available file kinds

WHERE:
  <file-spec>    :a string like: <file-kind>:<fpath>; use `-` <fpath> for STDIN.

EXAMPLES:
  rdecheck  f1:/foo/bar.csv  f2:/foo/baz.txt  -f1 f1:-
"""

import sys
import docopt


__package__ = 'rdechecker'  # @ReservedAssignment pep-366


def main(*args):
    from . import process_files
    from ._version import version

    opts = docopt.docopt(__doc__, *args, version=version)
    process_files(*opts['<file-spec>'], compress=opts['--compress'])


if __name__ == '__main__':
    main(*sys.argv)
