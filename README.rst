######################################################################
rdechecker: Validate & archive Real-Driving-Emissions files.
######################################################################

:release:       0.0.2
:date:          2017-12-22 04:53:35
:home:          https://github.com/JRCSTU/rdechecker/
:keywords:      rde, real-driving-emissions, vehicle-emissions, file-format, validation
:copyright:     2017 European Commission (`JRC <https://ec.europa.eu/jrc/>`_)
:license:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_

*rdechecker* validates files generated from Real-Driving-Emissions cycle tests,
before those files are submitted to monitoring bodies.
Optionally, archive and compress those files in a single HDF5 archive.

Quickstart
==========
Clone git repo and install in *develop* mode to experiment with sample files::

    git clone git+https://github.com/JRCSTU/rdechecker  rdechecker.git
    cd rdechecker.git/
    pip install -e .

(alternatively use: ``pip install git+https://github.com/JRCSTU/rdechecker.git``).

Run sample files (assumes git cloned locally, above)::

    $ cd rdechecker/tests/
    $ rdechek  f1:Sample_Data_Exchange_File.csv f2:Sample_Reporting_File_1.csv


Validation Rules
================
Currently partial CSV-cell validation *rules* are defined only for 2 file "kinds"::

    $ rdechek -l
    f1: Big file
    f2: The summary file

The rules are configured in the ``/rdechecker/tests/files-schema.yaml`` file.
They are defined in hierarachy:

- ``file_kinds.<file-kind>.lines`` or
- ``file_kinds.<file-kind>.sections.lines`` (for files with sections).

and they are keyed by the line-number (1-based).

For example::

                1: [TEST ID, '[code]', {req: null}]
                2: [Test date, '[dd.mm.yyyy]', {regex: '\d\d.\d\d.\d{4}'}]
                16: [Engine rated power, '[kW]', {float: null}]

which means that:

- line 1 must have at least 2 "cells" with the exact contents shown, plus
  a required last cell.
- line 2 in addition must have a 3rd cell that satisfy a "date" regular-expression.
- line 16  must have 2 fixed-string cells and a float 3rd one.

You may view all available rules with::

    $ rdechecker -l rules
    - str: equal the given text
    - _str: be missing or equal the given text
    - istr: equal(caseless) the given text
    - _istr: be missing or equal(caseless) the given text
    - regex: match the given regex
    - _regex: be missing or match the given regex
    - int: int(x=0) -> integer
    - _int: be missing or int(x=0) -> integer
    - float: float(x) -> floating point number
    - _float: be missing or float(x) -> floating point number
    - req: not be empty
    - _req: be missing or not be empty

.. Tip::
   When writting validations, extra care is needed with characters `:[],{}`
   (among others) because they have special meaning in *YAML*.
