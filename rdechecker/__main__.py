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
  rdecheck [--log=<level>] [-a] [-f=<fkind>] <file-spec>...
  rdecheck -l [fkinds | rules]
  rdecheck -V

WHERE:
  <file-spec>                   A string like: [<fkind>:]<fpath>.
                                Use `-` <fpath> for STDIN; use `rdecheck -l` to list
                                available file-kinds.
                                No need to specify <fkind> if `-f=<fkind>` given.
  -f=<fkind>, --fkind=<fkind>   Assume default <fkind> for all <file-spec> given.
  -a, --archive                 TODO: Archive all input files into an HDF5 archive [default: false]
  --log=<level>                 Set logging level to integer or string:
                                DEBUG:10, INFO:20, WARN:30, ERROR:40, FATAL:50
                                [default: INFO]
  -l, --list                    List available file-kinds and/or CSV cell-rules.
  -h, --help                    Show this screen.
  -V, --version                 Show program & validation-schema versions.

EXAMPLES:
  $ rdechek  -l
  f1: Big file
  f2: The summary file

  $ rdechek  f1:Sample_Data_Exchange_File.csv  f2:Sample_Reporting_File_1.csv
  15:33:26       : INFO:rdechecker:f1:Sample_Data_Exchange_File.csv: OK
  15:33:26       : INFO:rdechecker:f2:Sample_Reporting_File_1.csv: OK
"""

from collections import OrderedDict
import logging
import sys

import docopt

import functools as fnt


if __package__ is None:
    __package__ = 'rdechecker'  # @ReservedAssignment pep-366


def init_logging(level='DEBUG', frmt=None, color=True, **kw):
    try:
        level = int(level)
    except:
        pass
    if not frmt:
        frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
    logging.basicConfig(level=level, format=frmt, **kw)

    if color and sys.stderr.isatty():
        from rainbow_logging_handler import RainbowLoggingHandler

        color_handler = RainbowLoggingHandler(
            sys.stderr,
            color_message_debug=('grey', None, False),
            color_message_info=('blue', None, False),
            color_message_warning=('yellow', None, True),
            color_message_error=('red', None, True),
            color_message_critical=('white', 'red', True),
        )
        formatter = formatter = logging.Formatter(frmt)
        color_handler.setFormatter(formatter)

        ## Be conservative and apply color only when
        #  log-config looks like the "basic".
        #
        rlog = logging.getLogger()
        if rlog.handlers and isinstance(rlog.handlers[0], logging.StreamHandler):
            rlog.removeHandler(rlog.handlers[0])
            rlog.addHandler(color_handler)


def exit_with_pride(reason=None,
                    warn_color='\x1b[31;1m', err_color='\x1b[1m',
                    logger=None):
    """
    Return an *exit-code* and logs error/fatal message for ``main()`` methods.

    :param reason:
        - If reason is None, exit-code(0) signifying OK;
        - if exception,  print colorful (if tty) stack-trace, and exit-code(-1);
        - otherwise, prints str(reason) colorfully (if tty) and exit-code(1),
    :param warn_color:
        ansi color sequence for stack-trace (default: red)
    :param err_color:
        ansi color sequence for stack-trace (default: white-on-red)
    :param logger:
        which logger to use to log reason (must support info and fatal).

    :return:
        (0, 1 -1), for reason == (None, str, Exception) respectively.

    Note that returned string from ``main()`` are printed to stderr and
    exit-code set to bool(str) = 1, so print stderr separately and then
    set the exit-code.

    For colors use :meth:`RainbowLoggingHandler.getColor()`, defaults:
    - '\x1b[33;1m': yellow+bold
    - '\x1b[31;1m': red+bold

    Note: it's better to have initialized logging.
    """
    from . import log

    if reason is None:
        return 0
    if not logger:
        logger = log

    if isinstance(reason, BaseException):
        color = err_color
        exit_code = -1
        logmeth = fnt.partial(logger.fatal, exc_info=True)
    else:
        color = warn_color
        exit_code = 1
        logmeth = logger.error

    if sys.stderr.isatty():
        reset = '\x1b[0m'
        reason = '%s%s%s' % (color, reason, reset)

    logmeth(reason)
    return exit_code


def _build_infos(fkinds, rules):
    from . import RdeChecker, CellRules

    show_all = not (fkinds or rules)
    out = OrderedDict()
    if show_all or fkinds:
        rde = RdeChecker()
        l = rde.list_file_kinds()
        if show_all:
            out['fkinds'] = l
        else:
            out.update(l)
    if show_all or rules:
        l = CellRules().list_rules()
        if show_all:
            out['rules'] = l
        else:
            out.update(l)

    return out


def main(args=None):
    """
    :param args:
        Argument vector to be parsed, ``sys.argv[1:]`` if None
    """
    from . import AppException, SchemaError, log, RdeChecker, load_yaml, dump_yaml
    from ._version import version

    opts = docopt.docopt(__doc__,
                         argv=sys.argv[1:] if args is None else args)
    init_logging(level=opts['--log'])

    try:
        if opts['--version']:
            rde = RdeChecker()
            print(version, rde.schema_dict['version'])
        elif opts['--list']:
            out = _build_infos(opts['fkinds'], opts['rules'])
            dump_yaml(out, sys.stdout)
        else:
            rde = RdeChecker(*opts['<file-spec>'],
                             default_fkind=opts['--fkind'],
                             archive=opts['--archive'])
            rde.process_files()

        return 0
    except AppException as ex:
        log.debug('App exited due to: %r', ex, exc_info=1)
        ## Suppress stack-trace for "expected" errors but exit-code(1).
        msg = '%s%s\n  - %s' % (
            '%s: ' % type(ex).__name__ if isinstance(ex, SchemaError) else '',
            ex.args[0],
            '\n  - '.join(ex.args[1:]))
        return exit_with_pride(msg, logger=log)
    except Exception as ex:
        ## Log in DEBUG not to see exception x2, but log it anyway,
        #  in case log has been redirected to a file.
        log.debug('App failed due to: %r', ex, exc_info=1)
        ## Print stacktrace to stderr and exit-code(-1).
        return exit_with_pride(ex, logger=log)

if __name__ == '__main__':
    sys.exit(main())
