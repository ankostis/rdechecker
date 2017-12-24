# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from collections import OrderedDict
import logging
import re
import sys

import pkg_resources
from ruamel import yaml  # @UnresolvedImport

import functools as fnt
import pandas as pd

from ._version import version, __version__, __updated__
import io


log = logging.getLogger(__name__)

class AppException(Exception):
    pass

class SchemaError(AppException):
    pass


def load_yaml(finp, drop_comments=False, **kw):
    return yaml.load(finp,
                     Loader=yaml.Loader if drop_comments else yaml.RoundTripLoader,
                     **kw)


def dump_yaml(content, fout, drop_comments=False, **kw):
    return yaml.dump(content, fout,
                     Dumper=yaml.Dumper if drop_comments else yaml.RoundTripDumper,
                     **kw)


@fnt.lru_cache()
def read_jinja_template(fname):
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(
        loader=PackageLoader(__name__, package_path=''),
    )
    return env.get_template(fname).render()


_file_spec_regex = re.compile(r'^(?:(\w+):)?(.*)$')
def parse_file_spec(file_spec):
    m = _file_spec_regex.match(file_spec)
    if not m:
        raise AppException('Invalid file-spec %r!\n  Expected: <file-kind>:<fpath>' %
                           file_spec)
    return m.groups()


class CellRules:
    """
    Check CSV input-values (the "cells") against "cell-rules" templates.

    - A "cell-rule" can be either a plain string, or a single-kv-pair dictionary::

          {<rule-key>: <arg>}

      where:

        - <rule-key>   :one of the keys in :attr:`rule_funcs` map (see constructor).
        - <arg>        :(optional) arg to the rule's internal function

    - pure strings are simply checked for equality against the cell value.
    - any <rule-key> starting with underscore(`_`) denotes optionality:
      it is checked only if cell-value is not missing.
      NOTE that for CSVs, a missing value is the one between 2 consecutive
      commas (`,,`);  other symbols like `None`, `NA`, `-` are NOT missing
      (optionality check will fail)
    - TODO: multiple mappings ANDed together in the order declared
      (all must pass).

    The functions must raise, or return a transformed value (like *schema* library).

    A sample YAML for some csv row like that::

      - fixed string,
      - _istr, FOO
      - _int
      - req]
      - _req

    ...denotes a 5-cell CSV row:

      - 1st cell must equal to "fixed string"
      - 2nd cell must be "FOO" (case insensitively), or missing.
      - 3rd cell must be an integer with 2 digits (redundant)
      - 4th cell must not be missing or empty-string.
      - 5th cell must not be missing BUT can be the empty-string.

    Therefore, the following CSV-rows PASS::

          fixed string,,,anything,
          fixed string,,12,x,z
          "fixed string","FOO","00","x",""

    ...while the following CSV-rows FAIL::

          other string,,x,z
          fixed string ,,x,z
          fixed string,,-12
          fixed string,foo,00
          "fixed string","FOO",00,"","z"
          fixed string,FOO,00,x,
    """

    def __init__(self):
        self.rule_funcs = {
            'str': self._assert_equal,
            '_str': self._optional(self._assert_equal),
            'istr': self._assert_equal_ci,
            '_istr': self._optional(self._assert_equal_ci),
            'regex': self._assert_regex,     # Save Schema instance.
            '_regex': self._optional(self._assert_regex),
            'int': int,                     # Save Schema instance.
            '_int': self._optional(int),
            'float': float,
            '_float': self._optional(float),
            'req': self._assert_non_empty,
            '_req': self._optional(self._assert_non_empty),
        }

    def _assert_equal(self, exp, got):
        "equal the given text"
        if exp != got:
            raise AppException("%r does not equal %r!" % (got, exp))
        return got

    def _assert_equal_ci(self, exp, got):
        "equal(caseless) the given text"
        if exp != got:
            raise AppException("%r does not equal(caseless) %r!" % (got, exp))
        return got

    def _assert_regex(self, regex, got):
        "match the given regex"
        if not re.match(regex, got):
            raise AppException("%r does not match regex %r!" % (got, regex))
        return got

    def _assert_non_empty(self, got):
        "not be empty"
        if len(got) == 0:
            raise AppException("must not be empty!")
        return got

    def _optional(self, func):
        def checker(*args):
            cell = args[-1]
            if cell is not None:
                return func(*args)

        checker.__doc__ = "%s (or missing)" % func.__doc__
        return checker

    def _evaluate_rule(self, rule, arg, cell):
        try:
            func = self.rule_funcs[rule]
        except KeyError as ex:
            raise SchemaError("Unknown rule %r!" % rule,
                              "cell: %s" % cell,
                              "rule: %s(%s)" % (rule, arg or ''))

        args =(arg, cell) if arg else (cell,)

        ## Rule-functions scream when invalid.
        try:
            return func(*args)
        except AppException as ex:
            ex.args += ("cell: %s" % cell,
                        "rule: %s(%s)" % (rule, arg or ''))
            raise
        except Exception as ex:
            ex.args += ("cell: %s" % cell,
                        "rule: %s(%s)" % (rule, arg or ''))
            raise AppException(*ex.args)

    def validate_cell_rule(self, cell_rules, cell):
        if isinstance(cell_rules, dict):
            for rule, arg in cell_rules.items():
                cell = self._evaluate_rule(rule, arg, cell)
        elif isinstance(cell_rules, str):
            cell = self._evaluate_rule('str', cell_rules, cell)
        else:
            raise SchemaError("Unexpected type %s for cell-rules %r!"
                               "\n  One of (dict, string) expected." %
                               (type(cell_rules), cell_rules))

    def list_rules(self):
        return OrderedDict([(rule, func.__doc__.split('\n', maxsplit=1)[0])
                for rule, func in self.rule_funcs.items()])


class RdeChecker:
    def __init__(self, *file_specs,
                 default_fkind=None, archive=False, delimiter=','):
        self.cellcheck = CellRules()
        self.file_specs = file_specs
        self.archive = archive
        self.delimiter = delimiter
        self.schema_dict = self._read_files_schema()

        all_file_kinds = self.schema_dict['file_kinds']
        if default_fkind and default_fkind not in all_file_kinds:
            raise SchemaError('Unknown default file-fkind %r!\n  Must be one of %s' %
                             (default_fkind, tuple(all_file_kinds)))
        self.default_fkind = default_fkind

        if self.archive:
            raise NotImplemented('HDF5-archiving not ready yet.')

    def _read_files_schema(self):
        yml_txt = self.schema_dict = read_jinja_template('files-schema.yaml')
        return load_yaml(yml_txt, True)

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

    def _yield_sections(self, sections_schema, fp,
                       validate_section_breaks=True):
        """
        :param validate_section_breaks:
            If true, check that all section-nreak lines are "void",
            ie either empty or just full of delimiters.
        :return:
            A generator yielding for each section the tuple::

                (section-schema, section-lines)

            The start-line number `start` is 1-based.
        """
        sections_schema = sorted(sections_schema, key=lambda s: s['start'])
        sections_schema_iter = iter(sections_schema)

        def next_section_schema():
            sch = next(sections_schema_iter)
            end = sch.get('end') or float('inf')
            return sch, end

        section_schema, section_end = next_section_schema()
        section_lines = []

        def yield_section():
            nonlocal section_lines
            if section_lines:
                yield section_schema, section_lines
                section_lines = []

        break_indices = self._prepare_section_break_indices(sections_schema)
        break_indices = set(break_indices) if break_indices else ()

        for i, line in enumerate(fp, 1):
            try:
                if i in break_indices:
                    if (validate_section_breaks and
                        not self._is_section_break_line(line)):
                            raise AppException(
                                "Found a non-void section-break row:\n  %s" % line)
                else:
                    if i > section_end:  # Are we beyond end-of-section?
                        yield from yield_section()
                        ## Jump section.
                        section_schema, section_end = next_section_schema()

                        assert i == section_schema['start'], (
                            "Missed start of new section?", i, section_schema)
                    else:
                        assert i >= section_schema['start'], (
                            "Walking before new section?", i, section_schema)

                    section_lines.append(line)
            except Exception as ex:
                ex.args += ("row: %i" % i, )
                raise

        yield from yield_section()

    def _validate_line(self, r, line_schema, line):
        if line_schema:
            # FIXME: use pandas to parse CSV.
            for c, (cell_rules, cell) in enumerate(zip(line_schema, line)):
                if cell_rules:
                    try:
                        self.cellcheck.validate_cell_rule(cell_rules, cell)
                    except Exception as ex:
                        ex.args += ("column: %i" % c, "row: %i" % r)
                        raise

    def _validate_constraints_by_row(self, lines_schema, df, section_start=1):
        for r, l_schema in lines_schema.items():
            self._validate_line(r, l_schema, df.iloc[r - section_start, :].values)

    def _read_csv(self, kind_schema, inp):
        df_kw = kind_schema.get('df_kw', {})
        return pd.read_csv(inp, header=None, *df_kw)

    def validate_stream(self, kind_schema, fp):
        sections_schema = kind_schema.get('sections')
        if sections_schema:
            for s_schema, s_lines in self._yield_sections(sections_schema, fp):
                lines_schema = s_schema.get('lines')
                if lines_schema:
                    inp = io.StringIO(''.join(s_lines))
                    df = self._read_csv(kind_schema, inp)
                    start = s_schema['start']
                    self._validate_constraints_by_row(lines_schema, df, start)
        else:
            lines_schema = kind_schema.get('lines')
            if lines_schema:
                df = self._read_csv(kind_schema, fp)
                self._validate_constraints_by_row(lines_schema, df)

    def validate_filespec(self, file_spec):
        """
        When no files given, parse STDIN.
        """
        fkind, fpath = parse_file_spec(file_spec)
        if not fkind:
            if not self.default_fkind:
                raise AppException(
                    "No <fkind> deduced for file %r!"
                    "\n  Either specify it per-file <fkind>:<fpath> or "
                    "use default `-f=<fkind>`." % file_spec)
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
                log.debug('%r: validating...', fspec)
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
        return OrderedDict([(kind, props.get('description'))
                for kind, props in self.schema_dict['file_kinds'].items()])