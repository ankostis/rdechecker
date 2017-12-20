# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import re
import sys

import pkg_resources
from ruamel import yaml  # @UnresolvedImport

from ._version import version, __version__, __updated__


log = logging.getLogger(__name__)

class AppException(Exception):
    pass


def _parse_yaml(finp, drop_comments=False):
    return yaml.load(finp, yaml.Loader if drop_comments else yaml.RoundTripLoader)


_file_spec_regex = re.compile(r'^(?:(\w+):)?(.*)$')
def parse_file_spec(file_spec):
    m = _file_spec_regex.match(file_spec)
    if not m:
        raise AppException('Invalid file-spec %r!\n  Expected: <file-kind>:<fpath>' %
                           file_spec)
    return m.groups()


_cell_format_regex = re.compile(r'^(?:(int|float|re):)?(.*)$')
def validate_cell_format(cell_format, cell):
    # TODO: Use *schema* lbrary: https://pypi.python.org/pypi/schema/
    def assert_equal(exp, got):
        if exp != got:
            raise AppException('%r != %r' % (exp, got))

    def assert_regex(regex, got):
        if not re.match(regex, got):
            raise AppException('%r !~ %r' % (regex, got))

    dtype_funcs = {
        None: assert_equal,
        'int': int,
        'float': float,
        're': assert_regex,
    }
    m = _cell_format_regex.match(cell_format)
    dtype = m.group(1)
    arg = m.group(2)
    args = []
    func = dtype_funcs[dtype]
    if arg:
        args.append(arg)
    args.append(cell)
    ## Should scream if invalid....
    try:
        func(*args)
    except AppException:
        raise
    except Exception as ex:
        raise AppException(str(ex))

class RdeChecker:
    def __init__(self, *file_specs,
                 default_fkind=None, archive=False, delimiter=','):
        self.default_fkind = default_fkind
        self.file_specs = file_specs
        self.archive = archive
        self.delimiter = delimiter
        self._read_files_schema()

        if self.archive:
            raise NotImplemented('HDF5-archiving not ready yet.')

    def _read_files_schema(self):
        with pkg_resources.resource_stream(__name__,   # @UndefinedVariable
                                           'files-schema.yaml') as finp:
            self.schema_dict = _parse_yaml(finp, True)

    def _is_section_break_line(self, line):
        ## Delete all chars and expect line to be empty.
        line_break_chars = '\r\n%c' % self.delimiter
        line = line.translate(dict.fromkeys(ord(c) for c in line_break_chars))
        return line == ''


    def _prepare_section_break_indices(self, sections_schema):
        """
        Section-schema gets validated here, and thrown assertions.

        :param sections_schema:
            must be sorted by `start` offset
        :return:
            an ascending list of line-indices(1-based) for all section-breaks
        """
        assert sections_schema
        break_line_indices = []
        last_end = 0
        for i, section in enumerate(sections_schema):
            try:
                last_end is not None, ("Extraneous section after null-end!", section)

                start = section['start']
                assert start > last_end, ("Section overlap!", last_end, section)

                end = section.get('end')
                assert end is None or end > start, ("Zero-len section!", last_end, section)

                break_nlines = start - (last_end + 1)
                assert break_nlines >= 0, ("What??", break_nlines, last_end, section)

                break_line_indices.extend(list(range(last_end + 1, start)))

                last_end = end
            except Exception as ex:
                ex.args += ("schema-section no: %i" % i, )
                raise

        return break_line_indices

    def _yield_section_lines(self, sections_schema, fp):
        """
        :return:
            A generator yielding for each line the tuple::

                (i, line_schema, line)

            The line-number `i` is 1-based.
        """
        sections_schema = sorted(sections_schema, key=lambda s: s['start'])
        sections_schema_iter = iter(sections_schema)

        def next_section_schema():
            sch = next(sections_schema_iter)

            return sch, sch.get('lines')

        cur_schema, cur_lines_schema = next_section_schema()

        break_indices = self._prepare_section_break_indices(sections_schema)
        break_indices = set(break_indices) if break_indices else ()

        for i, line in enumerate(fp, 1):
            try:
                if i in break_indices:
                    if not self._is_section_break_line(line):
                        raise AppException(
                            "Found non-void section-break:\n  %s" %
                            (i, line))
                else:
                    if i > (cur_schema.get('end') or float('inf')):
                        ## Jump section.

                        cur_schema, cur_lines_schema = next_section_schema()
                        assert i == cur_schema['start'], (
                            "Jumped outside a section?", i, cur_schema)
                    else:
                        assert i >= cur_schema['start'], (
                            "Walking outside a section?", i, cur_schema)

                    yield i, cur_lines_schema and cur_lines_schema.get(i), line
            except Exception as ex:
                ex.args += ("line-no: %i" % i, )
                raise

    def _validate_line(self, r, line_schema, line):
        if line_schema:
            for c, (cell_format, cell) in enumerate(zip(line_schema,
                                                        line.split(self.delimiter))):
                if cell_format:
                    try:
                        validate_cell_format(cell_format, cell)
                    except Exception as ex:
                        ex.args += ("cell-format: %s" % cell_format,
                                    "column: %i" % c,
                                    "row: %i" % r)
                        raise

    def validate_stream(self, kind_schema, fp):
        sections_schema = kind_schema.get('sections')
        if sections_schema:
            for line_spec in self._yield_section_lines(sections_schema, fp):
                self._validate_line(*line_spec)
        else:
            lines_schema = kind_schema.get('lines')
            if lines_schema:
                for i, line in enumerate(fp, 1):
                    self._validate_line(i, lines_schema.get(i), line)

    def validate_filespec(self, file_spec):
        """
        When no files given, parse STDIN.
        """
        fkind, fpath = parse_file_spec(file_spec)
        if not fkind:
            if not self.default_fkind:
                raise AppException('No `-f` or per-file <fkind> given for file %r!' %
                                   file_spec)
            fkind = self.default_fkind

        all_file_kinds = self.schema_dict['file_kinds']
        try:
            kind_schema = all_file_kinds[fkind]
        except KeyError:
            raise AppException('Unknown file-fkind %r!\n  Must be one of %s' %
                             (fkind, tuple(all_file_kinds)))

        if fpath and fpath != '-':
            with open(fpath, 'rt') as fp:
                self.validate_stream(kind_schema, fp)
        else:
            self.validate_stream(kind_schema, sys.stdin)

    def process_files(self):
        for fspec in self.file_specs:
            try:
                self.validate_filespec(fspec)
                log.info('%s: OK', fspec)
            except OSError as ex:
                raise AppException('%s: %s' % (type(ex).__name__, str(ex)),
                                   "file-spec: %r" % fspec) from ex
                raise
            except Exception as ex:
                ex.args += ("file-spec: %r" % fspec, )
                raise

    def list_file_kinds(self):
        return '\n'.join('%s: %s' % (kind, props.get('description'))
                         for kind, props in self.schema_dict['file_kinds'].items())