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


_file_spec_regex = re.compile('^(\w+):(.*)$')
def parse_file_spec(file_spec):
    m = _file_spec_regex.match(file_spec)
    if not m:
        raise AppException('Invalid file-spec %r!\n  Expected: <file-kind>:<fpath>' %
                           file_spec)
    return m.groups()


class RdeChecker:
    def __init__(self, *file_specs, archive=False, delimiter=','):
        self.file_specs = file_specs
        self.archive = archive
        self.delimiter = delimiter
        self._read_files_schema()

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
        :param sections_schema:
            must be sorted by `start` line
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
                ex.args += ("  schema-section no: %i" % i, )
                raise

        return break_line_indices

    def _split_sections(self, sections_schema, fp):
        break_indices = self._prepare_section_break_indices(sections_schema)
        break_indices = set(break_indices) if break_indices else ()

        sections = []
        prev_section_i = -1  # Ensure 1st section considered "jump" below.
        for i, line in enumerate(fp, 1):
            if i in break_indices:
                if not self._is_section_break_line(line):
                    raise AppException(
                        "Found non-void section-break line no-%i: %s" %
                        (i, line))
            else:
                if i > prev_section_i + 1:
                    ## Jumped section:
                    cur_section = []
                    sections.append(cur_section)

                cur_section.append(line)
                prev_section_i = i

        print([len(s) for s in sections])

        return sections

    def validate_stream(self, kind_schema, fp):
        sections_schema = kind_schema.get('sections')
        if sections_schema:
            sections_schema = sorted(sections_schema, key=lambda s: s['start'])
            self._split_sections(sections_schema, fp)
        else:
            raise NotImplemented('Only sectioned files supported yet')

    def validate_filespec(self, file_spec):
        """
        When no files given, parse STDIN.
        """
        kind, fpath = parse_file_spec(file_spec)
        all_file_kinds = self.schema_dict['file_kinds']
        try:
            kind_schema = all_file_kinds[kind]
        except KeyError:
            raise AppException('Unknown file-kind %r!\n  Must be one of %s' %
                             (kind, tuple(all_file_kinds)))

        if fpath and fpath != '-':
            with open(fpath, 'rt') as fp:
                self.validate_stream(kind_schema, fp)
        else:
            self.validate_stream(kind_schema, sys.stdin)

    def process_files(self):
        if not self.file_specs:
            raise AppException('No file-spec given!')

        for fspec in self.file_specs:
            self.validate_filespec(fspec)