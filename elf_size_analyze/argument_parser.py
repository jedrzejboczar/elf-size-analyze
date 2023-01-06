"""
Argument parser for package
"""

import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="""
Prints report of memory usage of the given executable.
Shows how different source files contribute to the total size.
Uses inforamtion contained in ELF executable and binutils programs.
For best results the program should be compiled with maximum debugging information
(e.g. GCC flag: `-g`, or more: `-ggdb3`).
    """, epilog="""
This script is based on 'size_report' script from Zephyr Project:
https://github.com/zephyrproject-rtos/zephyr (scripts/footprint/size_report).
    """)

    parser.add_argument('elf', metavar='ELF_FILE',
                        help='path to the examined ELF file')

    memory_group = parser.add_argument_group(
        'Memory type', """
Specifies memory types for which statistics should be printed.
Choosing at least one of these options is required.
RAM/ROM options may be oversimplifed for some targets, under the hood they just filter the symbols
by sections in the following manner:
sections must have ALLOC flag and: for RAM - have WRITE flag, for ROM - not have NOBITS type.
        """)
    memory_group.add_argument('-R', '--ram', action='store_true',
                              help='print RAM statistics')
    memory_group.add_argument('-F', '--rom', action='store_true',
                              help='print ROM statistics ("Flash")')
    memory_group.add_argument('-P', '--print-sections', action='store_true',
                              help='print section headers that can be used for filtering symbols with -S option'
                              + ' (output is almost identical to `readelf -WS ELF_FILE`)')
    memory_group.add_argument('-S', '--use-sections', nargs='+', metavar='NUMBER',
                              help='manually select sections from which symbols will be used (by number)')

    basic_group = parser.add_argument_group(
        'Basic arguments')
    basic_group.add_argument('-t', '--toolchain-triplet', '--toolchain-path',
                             default='', metavar='PATH',
                             help='toolchain triplet/path to prepend to binutils program names,'
                             + ' this is important for examining cross-compiled ELF files,'
                             + ' e.g `arm-none-eabi-` or `/my/path/arm-none-eabi-` or `/my/path/`')
    basic_group.add_argument('-v', '--verbose', action='count',
                             help='increase verbosity, can be specified up to 3 times'
                             + ' (versobity levels: ERROR -> WARNING -> INFO -> DEBUG)')

    printing_group = parser.add_argument_group(
        'Printing options', 'Options for changing the output formatting.')
    printing_group.add_argument('-w', '--max-width', default=80, type=int,
                                help='set maximum output width, 0 for unlimited width (default 80)')
    printing_group.add_argument('-m', '--min-size', default=0, type=int,
                                help='do not print symbols with size below this value')
    printing_group.add_argument('-f', '--fish-paths', action='store_true',
                                help='when merging paths, use fish-like method to shrink them')
    printing_group.add_argument('-s', '--sort-by-name', action='store_true',
                                help='sort symbols by name instead of sorting by size')
    printing_group.add_argument('-H', '--human-readable', action='store_true',
                                help='print sizes in human readable format')
    printing_group.add_argument('-o', '--files-only', action='store_true',
                                help='print only files (to be used with cumulative size enabled)')
    printing_group.add_argument('-a', '--alternating-colors', action='store_true',
                                help='use alternating colors when printing symbols')
    printing_group.add_argument('-j', '--json', action='store_true',
                                help='create json output')
    printing_group.add_argument('-W', '--html', action='store_true',
                                help='create HTML output')
    printing_group.add_argument('-c', '--css',
                                help='path to custom css for HTML output')                                

    printing_group.add_argument('--no-demangle', action='store_true',
                                help='disable demangling of C++ symbol names')
    printing_group.add_argument('--no-merge-paths', action='store_true',
                                help='disable merging paths in the table')
    printing_group.add_argument('--no-color', action='store_true',
                                help='disable colored output')
    printing_group.add_argument('--no-cumulative-size', action='store_true',
                                help='disable printing of cumulative sizes for paths')
    printing_group.add_argument('--no-totals', action='store_true',
                                help='disable printing the total symbols size')

    args = parser.parse_args()

    return args
