# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Validate & archive Real-Driving-Emissions CSV-files (TODO: Excel).

USAGE:
  rdecheck [--log=<level>] [--archive] <file-spec> ...
  rdecheck -l

WHERE:
  <file-spec>       :a string like: <file-kind>:<fpath>; use `-` <fpath> for STDIN;
                    use `-l` to see available kfile-kinds.
  --archive         :archive all input files into an HDF5 archive [default: false]
  -l                :list available file kinds
  --log=<level>     :an integer: DEBUG, INFO, WARN, ERROR, FATAL <--> 10, 20, 30, 40 50
                     [default: 20]

EXAMPLES:
  rdecheck  f1:/foo/bar.csv  f2:/foo/baz.txt  -f1 f1:-
"""

import logging
import sys

import docopt


__package__ = 'rdechecker'  # @ReservedAssignment pep-366


def init_logging(level='DEBUG', **kw):
    try:
        level = int(level)
    except:
        pass
    logging.basicConfig(level=level, **kw)

def main(*args):
    from . import RdeChecker
    from ._version import version

    opts = docopt.docopt(__doc__, *args, version=version)
    init_logging(level=opts['--log'])

    rde = RdeChecker(*opts['<file-spec>'], archive=opts['--archive'])
    rde.process_files()


if __name__ == '__main__':
    main(*sys.argv)
