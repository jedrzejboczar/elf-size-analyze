"""
The symbol class
"""

import logging
import os
import re
import subprocess

from elf_size_analyze.misc import named_group

log = logging.getLogger('elf-size-analyze')

class Symbol:
    """
    Represents a linker symbol in an ELF file. Attributes are as in the output
    of readelf command. Additionally, has optional file path and line number.
    """

    def __init__(self, num, name, value, size, type, bind, visibility, section,
                 file=None, line=None):
        self.num = num
        self.name = name
        self.value = value
        self.size = size
        self.type = type
        self.bind = bind
        self.visibility = visibility
        self.section = section
        self.file = file
        self.line = line

    def __repr__(self):
        return 'Symbol(%s)' % (self.name, )

    # Regex for parsing readelf output lines
    # Readelf output should look like the following:
    #   Symbol table '.symtab' contains 623 entries:
    #      Num:    Value  Size Type    Bind   Vis      Ndx Name
    #        0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND
    #   ...
    #      565: 08002bf9     2 FUNC    WEAK   DEFAULT    2 TIM2_IRQHandler
    #      566: 200002a8    88 OBJECT  GLOBAL DEFAULT    8 hspi1
    pattern_fields = [
        r'\s*',
        named_group('num', r'\d+'), r':',
        r'\s+',
        named_group('value', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('size', r'(0x)?[0-9A-Fa-f][0-9A-Fa-f]*'), # accept dec & hex numbers
        r'\s+',
        named_group('type', r'\S+'),
        r'\s+',
        named_group('bind', r'\S+'),
        r'\s+',
        named_group('visibility', r'\S+'),
        r'\s+',
        named_group('section', r'\S+'),
        r'\s+',
        named_group('name', r'.*'),
    ]
    pattern = r'^{}$'.format(r''.join(pattern_fields))
    pattern = re.compile(pattern)

    @classmethod
    def from_readelf_line(cls, line,
                          ignored_types=['NOTYPE', 'SECTION', 'FILE'],
                          ignore_zero_size=True):
        """
        Create a Symbol from a line of `readelf -Ws` output.
        """
        m = cls.pattern.match(line)
        if not m:
            log.debug('no match: ' + line.strip())
            return None

        # convert non-string values
        m = m.groupdict()
        m['num'] = int(m['num'])
        m['value'] = int(m['value'], 16)
        m['size'] = int(m['size']) if m['size'].isdecimal() else int(m['size'], 16)
        try:  # for numeric sections
            m['section'] = int(m['section'])
        except ValueError:
            pass

        # ignore if needed
        if not m['name'].strip() \
                or m['type'].lower() in map(str.lower, ignored_types) \
                or (ignore_zero_size and m['size'] == 0):
            log.debug('ignoring: ' + line.strip())
            return None

        # create the Symbol
        s = Symbol(**m)

        return s

    @classmethod
    def extract_elf_symbols_info(cls, elf_file, readelf_exe='readelf'):
        """
        Uses binutils 'readelf' to find info about all symbols from an ELF file.
        """
        flags = ['--wide', '--syms']
        readelf_proc = subprocess.Popen([readelf_exe, *flags, elf_file],
                                        stdout=subprocess.PIPE, universal_newlines=True)

        # parse lines
        log.info('Using readelf symbols regex: %s' % cls.pattern.pattern)
        symbols = [Symbol.from_readelf_line(l) for l in readelf_proc.stdout]
        n_ignored = len(list(filter(lambda x: x is None, symbols)))
        symbols = list(filter(None, symbols))

        if readelf_proc.wait(3) != 0:
            raise subprocess.CalledProcessError(readelf_proc.returncode,
                                                readelf_proc.args)

        log.info('ignored %d/%d symbols' % (n_ignored, len(symbols) + n_ignored))

        return symbols


def detect_nm_is_llvm(nm_exe):
    proc = subprocess.run([nm_exe, '--version'],
                          check=True, capture_output=True, universal_newlines=True)
    if proc.stdout.lower().find('llvm') >= 0:
        return True
    # startswith(), not find() because llvm-nm contains "compatible with GNU nm"
    if not proc.stdout.lower().strip().startswith('gnu nm'):
        log.warning('Could not detect nm version, assuming GNU nm')
    return False


def extract_elf_symbols_fileinfo(elf_file, nm_exe='nm'):
    """
    Uses binutils 'nm' to find files and lines where symbols from an ELF
    executable were defined.
    """
    # Regex for parsing nm output lines
    # We use Posix mode, so lines should be in form:
    #   NAME TYPE VALUE SIZE[\tFILE[:LINE]]
    # e.g.
    #   MemManage_Handler T 08004130 00000002	/some/path/file.c:80
    #   memset T 08000bf0 00000010
    gnu_flags = ['--portability', '--line-numbers']
    llvm_flags = ['--portability', '--print-file-name']
    gnu_fields = [
        named_group('name', r'\S+'),
        r'\s+',
        named_group('type', r'\S+'),
        r'\s+',
        named_group('value', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('size', r'[0-9a-fA-F]+'),
        named_group('fileinfo', r'.*'),
    ]
    # llvm-nm version of output:
    #   /some/path/file.c: memset t 800a2ea 6e
    llvm_fields = [
        named_group('fileinfo', r'[^:]*'),
        r':\s+',
        named_group('name', r'\S+'),
        r'\s+',
        named_group('type', r'\S+'),
        r'\s+',
        named_group('value', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('size', r'[0-9a-fA-F]+'),
    ]

    is_llvm = detect_nm_is_llvm(nm_exe)
    flags, fields = (llvm_flags, llvm_fields) if is_llvm else (gnu_flags, gnu_fields)

    pattern = r'^{}$'.format(r''.join(fields))
    pattern = re.compile(pattern)
    log.info('Using nm symbols regex: %s' % pattern.pattern)

    nm_proc = subprocess.Popen([nm_exe, *flags, elf_file],
                               stdout=subprocess.PIPE, universal_newlines=True)

    # process nm output
    fileinfo_dict = {}
    for line in nm_proc.stdout:
        m = pattern.match(line)
        if not m:
            continue

        # parse the file info
        file, line = None, None
        fileinfo = m.group('fileinfo').strip()
        if len(fileinfo) > 0:
            # check for line number
            line_i = fileinfo.rfind(':')
            if line_i >= 0:
                file = fileinfo[:line_i]
                line = int(fileinfo[line_i + 1])
            else:
                file = fileinfo
            # try to make the path more readable
            file = os.path.normpath(file)

        fileinfo_dict[m.group('name')] = file, line

    if nm_proc.wait(3) != 0:
        raise subprocess.CalledProcessError(nm_proc.returncode,
                                            nm_proc.args)

    return fileinfo_dict


def add_fileinfo_to_symbols(fileinfo_dict, symbols_list):
    # use dictionary for faster access (probably)
    symbols_dict = {s.name: s for s in symbols_list}
    for symbol_name, (file, line) in fileinfo_dict.items():
        if file is None and line is None:
            continue
        if symbol_name in symbols_dict:
            symbol = symbols_dict[symbol_name]
            symbol.file = file
            symbol.line = line
        else:
            log.warning('nm found fileinfo for symbol "%s", which has not been found by readelf'
                            % symbol_name)


def demangle_symbol_names(symbols, cppfilt_exe='c++filt'):
    """
    Use c++filt to demangle symbol names in-place.
    """
    flags = []
    cppfilt_proc = subprocess.Popen(
        [cppfilt_exe, *flags], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)

    for symbol in symbols:
        # write the line and flush it
        # not super-efficient but writing all at once for large list of symbols
        # can block the program (probably due to buffering)
        cppfilt_proc.stdin.write((symbol.name + '   \n'))
        cppfilt_proc.stdin.flush()
        new_name = cppfilt_proc.stdout.readline().strip()
        symbol.name = new_name
    cppfilt_proc.stdin.close()

    if cppfilt_proc.wait(3) != 0:
        raise subprocess.CalledProcessError(cppfilt_proc.returncode,
                                            cppfilt_proc.args)
