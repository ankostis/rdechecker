# -*- coding: utf-8 -*-
# !/usr/bin/env python
#
# Copyright 2017 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import re
import sys

import pkg_resources
from ruamel import yaml  # @UnresolvedImport

from ._version import version, __version__, __updated__
from flask.cli import NoAppException


class AppException(Exception):
    pass


def parse_yaml(finp, drop_comments=False):
    return yaml.load(finp, yaml.Loader if drop_comments else yaml.RoundTripLoader)


def validate_sections(schema, fp, compress):
    sections = schema['sections']
    last_section = sections[-1]
    last_head_line = last_section['start']

    import itertools as itt

    head = ''.join(i[1] for i in zip(range(last_head_line +1), fp))

    print(head)


_file_spec_regex = re.compile('^(\w+?) *: *(.*)$')


def parse_file_spec(file_spec):
    m = _file_spec_regex.match(file_spec)
    if not m:
        raise AppException('Invalid file-spec %r!\n  Expected: <file-kind>:<fpath>' %
                           file_spec)
    return m.groups()


def validate_file(schema_dict, file_spec, compress=False):
    """
    When no files given,. parse STDIN.
    """
    kind, fpath = parse_file_spec(file_spec)
    all_file_kinds = schema_dict['file_kinds']
    try:
        kind_schema = all_file_kinds[kind]
    except KeyError:
        raise AppException('Unknown file-kind %r!\n  Must be one of %s' %
                         (kind, tuple(all_file_kinds)))

    if fpath and fpath != '-':
        with open(fpath, 'rt') as fp:
            validate_sections(kind_schema, fp, compress=compress)
    else:
        validate_sections(kind_schema, sys.stdin, compress=compress)


def process_files(*file_specs, compress=False):
    if not file_specs:
        raise AppException('No file-spec given!')

    with pkg_resources.resource_stream(__name__, 'schema.yaml') as finp:  # @UndefinedVariable
        schema_dict = parse_yaml(finp, True)

    for fspec in file_specs:
        validate_file(schema_dict, fspec, compress=compress)