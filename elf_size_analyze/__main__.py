#!/usr/bin/env python3
#
# Copyright (c) 2016, Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# Based on a script by:
#       Chereau, Fabien <fabien.chereau@intel.com>

# ^originial comments before my modifications
# This script is based on 'size_report' from Zephyr Project scripts:
#   https://github.com/zephyrproject-rtos/zephyr/blob/master/scripts/footprint/size_report
#
# It has been modified to be more flexible for different (also not-bare-metal) ELF files,
# and adds some more data visualization options. Parsing has been updated to use
# regular expressions as it is much more robust solution.

import itertools
import json
import logging
import math
import os
import platform
import shutil
import sys

from elf_size_analyze.argument_parser import parse_args
from elf_size_analyze.section import Section
from elf_size_analyze.symbol import (Symbol, add_fileinfo_to_symbols,
                                     demangle_symbol_names,
                                     extract_elf_symbols_fileinfo)
from elf_size_analyze.symbol_tree import SymbolsTreeByPath
from elf_size_analyze.html.gen import generate_html_output

# default logging configuration
log = logging.getLogger('elf-size-analyze')
console = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(message)s')
console.setFormatter(formatter)
log.setLevel(logging.ERROR)
log.addHandler(console)


def main():
    result = 1
    args = parse_args()

    # adjust verbosity
    if args.verbose:
        level = log.level - 10 * args.verbose
        log.setLevel(max(level, logging.DEBUG))

    # prepare arguments
    if not os.path.isfile(args.elf):
        print('ELF file %s does not exist' % args.elf, file=sys.stderr)
        return result

    if not any([args.rom, args.ram, args.print_sections, args.use_sections]):
        print('No memory type action specified (RAM/ROM or special). See -h for help.')
        return result

    def get_exe(name):
        cmd = args.toolchain_triplet + name
        if 'Windows' == platform.system():
            cmd = cmd + '.exe'
        assert shutil.which(cmd) is not None, \
            'Executable "%s" could not be found!' % cmd
        return args.toolchain_triplet + name

    # process symbols
    symbols = Symbol.extract_elf_symbols_info(args.elf, get_exe('readelf'))
    fileinfo = extract_elf_symbols_fileinfo(args.elf, get_exe('nm'))
    add_fileinfo_to_symbols(fileinfo, symbols)

    # demangle only after fileinfo extraction!
    if not args.no_demangle:
        demangle_symbol_names(symbols, get_exe('c++filt'))

    # load section info
    sections = Section.extract_sections_info(args.elf, get_exe('readelf'))
    sections_dict = {sec.num: sec for sec in sections}

    def prepare_tree(symbols):
        tree = SymbolsTreeByPath(symbols)
        if not args.no_merge_paths:
            tree.merge_paths(args.fish_paths)
        if not args.no_cumulative_size:
            tree.accumulate_sizes()
        if args.sort_by_name:
            tree.sort(key=lambda symbol: symbol.name, reverse=False)
        else:  # sort by size
            tree.sort(key=lambda symbol: symbol.size, reverse=True)
        if not args.no_totals:
            tree.calculate_total_size()

        return tree

    def print_tree(header, tree):
        min_size = math.inf if args.files_only else args.min_size
        lines = tree.generate_printable_lines(
            header=header, colors=not args.no_color, human_readable=args.human_readable,
            max_width=args.max_width, min_size=min_size, alternating_colors=args.alternating_colors)
        for line in lines:
            line.print()

    def print_json(header, tree):
        min_size = math.inf if args.files_only else args.min_size
        nodedict = tree._generate_node_dict(min_size=min_size)

        print(json.dumps(nodedict))

    def print_html(header, tree):
        min_size = math.inf if args.files_only else args.min_size
        nodedict = tree._generate_node_dict(min_size=min_size)
        title = f"ELF size information for {os.path.basename(args.elf)} - {header}"
        html = generate_html_output(nodedict, title, args.css)
        print(html)


    def filter_symbols(section_key):
        secs = filter(section_key, sections)
        secs_str = ', '.join(s.name for s in secs)
        log.info('Considering sections: ' + secs_str)
        filtered = filter(lambda symbol: section_key(sections_dict.get(symbol.section, None)),
                          symbols)
        out, test = itertools.tee(filtered)
        if len(list(test)) == 0:
            print("""
ERROR: No symbols from given section found or all were ignored!
       Sections were: %s
            """.strip() % secs_str, file=sys.stderr)
            sys.exit(1)
        return out

    if args.print_sections:
        Section.print(sections)

    if args.json:
        print_func = print_json
    elif args.html:
        print_func = print_html
    else:
        print_func = print_tree

    if args.rom:
        print_func('ROM', prepare_tree(filter_symbols(lambda sec: sec and sec.occupies_rom())))

    if args.ram:
        print_func('RAM', prepare_tree(filter_symbols(lambda sec: sec and sec.occupies_ram())))

    if args.use_sections:
        nums = list(map(int, args.use_sections))
        #  secs = list(filter(lambda s: s.num in nums, sections))
        name = 'SECTIONS: %s' % ','.join(map(str, nums))
        print_func(name, prepare_tree(filter_symbols(lambda sec: sec and sec.num in nums)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
