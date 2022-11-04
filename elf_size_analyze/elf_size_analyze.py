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
# It has been modified to be more flexible for different (also not-bare-metal)
# ELF files, and adds some more data visualization options. Parsing has been
# updated to use regular expressions as it is much more robust solution.

import os
import sys
import json
import math
import shutil
import logging

import itertools
import platform

from elf_size_analyze.misc.section import Section
from elf_size_analyze.misc.symbol import (
    Symbol,
    SymbolsTreeByPath,
    add_fileinfo_to_symbols,
    demangle_symbol_names,
    extract_elf_symbols_fileinfo,
)
from elf_size_analyze.misc.argument_parser import parse_args

# default logging configuration
log = logging.getLogger("elfSizeAnalyze")
console = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(message)s")
console.setFormatter(formatter)
log.setLevel(logging.ERROR)
log.addHandler(console)

##############################################################################


def main():
    result = False
    args = parse_args()

    # adjust verbosity
    if args.verbose:
        level = log.level - 10 * args.verbose
        log.setLevel(max(level, logging.DEBUG))

    # prepare arguments
    if not os.path.isfile(args.elf):
        print("ELF file %s does not exist" % args.elf, file=sys.stderr)
        return result

    if not any([args.rom, args.ram, args.print_sections, args.use_sections]):
        print(
            "No memory type action specified (RAM/ROM or special). See -h for help."
        )
        return result

    def get_exe(name):
        cmd = args.toolchain_triplet + name
        if "Windows" == platform.system():
            cmd = cmd + ".exe"
        assert shutil.which(cmd) is not None, (
            'Executable "%s" could not be found!' % cmd
        )
        return args.toolchain_triplet + name

    # process symbols
    symbols = Symbol.extract_elf_symbols_info(args.elf, get_exe("readelf"))
    fileinfo = extract_elf_symbols_fileinfo(args.elf, get_exe("nm"))
    add_fileinfo_to_symbols(fileinfo, symbols)

    # demangle only after fileinfo extraction!
    if not args.no_demangle:
        demangle_symbol_names(symbols, get_exe("c++filt"))

    # load section info
    sections = Section.extract_sections_info(args.elf, get_exe("readelf"))
    sections_dict = {sec.num: sec for sec in sections}

    def print_tree(header, symbols):
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
        min_size = math.inf if args.files_only else args.min_size
        lines = tree.generate_printable_lines(
            header=header,
            colors=not args.no_color,
            human_readable=args.human_readable,
            max_width=args.max_width,
            min_size=min_size,
            alternating_colors=args.alternating_colors,
        )
        for line in lines:
            line.print()

    def create_json(header, symbols):
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
        min_size = math.inf if args.files_only else args.min_size
        nodedict = tree._generate_node_dict(min_size=min_size)
        with open(
            args.elf.replace(".elf", "") + "_" + header + "Analysis.json", "w"
        ) as jsonFile:
            json.dump(nodedict, jsonFile)

    def filter_symbols(section_key):
        secs = filter(section_key, sections)
        secs_str = ", ".join(s.name for s in secs)
        log.info("Considering sections: " + secs_str)
        filtered = filter(
            lambda symbol: section_key(
                sections_dict.get(symbol.section, None)
            ),
            symbols,
        )
        out, test = itertools.tee(filtered)
        if len(list(test)) == 0:
            print(
                """
ERROR: No symbols from given section found or all were ignored!
       Sections were: %s
            """.strip()
                % secs_str,
                file=sys.stderr,
            )
            sys.exit(1)
        return out

    if args.print_sections:
        Section.print(sections)

    if args.rom:
        if args.json:
            create_json(
                "ROM", filter_symbols(lambda sec: sec and sec.occupies_rom())
            )
        else:
            print_tree(
                "ROM", filter_symbols(lambda sec: sec and sec.occupies_rom())
            )

    if args.ram:
        if args.json:
            create_json(
                "RAM", filter_symbols(lambda sec: sec and sec.occupies_ram())
            )
        else:
            print_tree(
                "RAM", filter_symbols(lambda sec: sec and sec.occupies_ram())
            )

    if args.use_sections:
        nums = list(map(int, args.use_sections))
        #  secs = list(filter(lambda s: s.num in nums, sections))
        name = "SECTIONS: %s" % ",".join(map(str, nums))
        print_tree(name, filter_symbols(lambda sec: sec and sec.num in nums))

    return True


if __name__ == "__main__":
    result = main()
    if not result:
        sys.exit(1)
