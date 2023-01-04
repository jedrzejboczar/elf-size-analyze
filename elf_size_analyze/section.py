"""
The section class
"""

import logging
import re
import subprocess

from elf_size_analyze.color import Color
from elf_size_analyze.misc import named_group, sizeof_fmt

log = logging.getLogger('elf-size-analyze')

# Some nice info about sections in ELF files:
# http://www.sco.com/developers/gabi/2003-12-17/ch4.sheader.html#sh_flags
class Section:
    """Represents an ELF file section as read by `readelf -WS`."""

    # Regex for parsing readelf sections information
    # Example output:
    #   Section Headers:
    #     [Nr] Name              Type            Addr     Off    Size   ES Flg Lk Inf Al
    #     [ 0]                   NULL            00000000 000000 000000 00      0   0  0
    #     [ 1] .isr_vector       PROGBITS        08000000 010000 000188 00   A  0   0  1
    #     [ 2] .text             PROGBITS        08000190 010190 00490c 00  AX  0   0 16
    #     [ 3] .rodata           PROGBITS        08004aa0 014aa0 000328 00   A  0   0  8
    # Regex test: https://regex101.com/r/N3YQYw/1
    pattern_fields = [
        r'\s*',
        r'\[\s*', named_group('num', r'\d+'), r'\]',
        r'\s+',
        named_group('name', r'\S+'),
        r'\s+',
        named_group('type', r'\S+'),
        r'\s+',
        named_group('address', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('offset', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('size', r'[0-9a-fA-F]+'),
        r'\s+',
        named_group('entry_size', r'[0-9a-fA-F]+'),  # whatever it is we don't need it
        r'\s+',
        named_group('flags', r'\S*'),
        r'\s+',
        named_group('link', r'[0-9a-fA-F]+'),  # whatever it is we don't need it
        r'\s+',
        named_group('info', r'[0-9a-fA-F]+'),  # whatever it is we don't need it
        r'\s+',
        named_group('alignment', r'[0-9a-fA-F]+'),  # whatever it is we don't need it
        r'\s*'
    ]
    pattern = r'^{}$'.format(r''.join(pattern_fields))
    pattern = re.compile(pattern)

    class Flag:
        # key to flags
        WRITE = 'W'
        ALLOC = 'A'
        EXECUTE = 'X'
        MERGE = 'M'
        STRINGS = 'S'
        INFO = 'I'
        LINK_ORDER = 'L'
        EXTRA_OS_PROCESSING_REQUIRED = 'O'
        GROUP = 'G'
        TLS = 'T'
        COMPRESSED = 'C'
        UNKNOWN = 'x'
        OS_SPECIFIC = 'o'
        EXCLUDE = 'E'
        PURECODE = 'y'
        PROCESSOR_SPECIFIC = 'p'
        PPC_VLE = 'v'
        GNU_MBIND = 'D'
        X86_64_LARGE = 'l'
        GNU_RETAIN = 'R'

        @classmethod
        def to_string(cls, flag):
            for name, value in vars(cls).items():
                if not name.startswith('_'):
                    if value == flag:
                        return name
            return None

    def __init__(self, **kwargs):
        self.num = kwargs['num']
        self.name = kwargs['name']
        self.type = kwargs['type']
        self.address = kwargs['address']
        self.offset = kwargs['offset']
        self.size = kwargs['size']
        self.entry_size = kwargs['entry_size']
        self.flags = kwargs['flags']
        self.link = kwargs['link']
        self.info = kwargs['info']
        self.alignment = kwargs['alignment']

    def is_writable(self):
        return self.Flag.WRITE in self.flags

    def occupies_memory(self):
        # these are the only relevant sections for us
        return self.Flag.ALLOC in self.flags

    # these two methods are probably a big simplification
    # as they may be true only for small embedded systems
    def occupies_rom(self):
        return self.occupies_memory() and \
            self.type not in ['NOBITS']

    def occupies_ram(self):
        return self.occupies_memory() and self.is_writable()

    @classmethod
    def from_readelf_line(cls, line):
        """
        Create a Section from a line of `readelf -WS` output.
        """
        m = cls.pattern.match(line)
        if not m:
            log.debug('no match: ' + line.strip())
            return None

        # convert non-string values
        m = m.groupdict()
        m['num'] = int(m['num'])
        m['address'] = int(m['address'], 16)
        m['offset'] = int(m['offset'], 16)
        m['size'] = int(m['size'], 16)
        m['entry_size'] = int(m['entry_size'], 16)
        # not sure if these are base-16 or base-10
        m['link'] = int(m['link'], 10)
        m['info'] = int(m['info'], 10)
        m['alignment'] = int(m['alignment'], 10)

        return Section(**m)

    @classmethod
    def print(cls, sections):
        lines = []
        for s in sections:
            fields = [str(s.num), s.name, s.type,
                      hex(s.address), sizeof_fmt(s.size),
                      ','.join(cls.Flag.to_string(f) for f in s.flags)]
            lines.append(fields)
        sizes = [max(len(l[i]) for l in lines) for i in range(6)]
        h_fmt = '{:%d}   {:%d}   {:%d}   {:%d}   {:%d}   {:%d}' % (*sizes, )
        fmt = '{:>%d}   {:%d}   {:%d}   {:>%d}   {:>%d}   {:%d}' % (*sizes, )
        header = h_fmt.format('N', 'Name', 'Type', 'Addr', 'Size', 'Flags')
        separator = '=' * len(header)
        top_header = '{:=^{size}s}'.format(' SECTIONS ', size=len(separator))
        print(Color.BOLD + top_header  + Color.RESET)
        print(Color.BOLD + header + Color.RESET)
        print(Color.BOLD + separator  + Color.RESET)
        for line in lines:
            print(fmt.format(*line))
        print(Color.BOLD + separator  + Color.RESET)

    @classmethod
    def extract_sections_info(cls, elf_file, readelf_exe='readelf'):
        """
        Uses binutils 'readelf' to find info about all sections from an ELF file.
        """
        flags = ['--wide', '--section-headers']
        readelf_proc = subprocess.Popen([readelf_exe, *flags, elf_file],
                                        stdout=subprocess.PIPE, universal_newlines=True)

        # parse lines
        log.info('Using readelf sections regex: %s' % cls.pattern.pattern)
        sections = [Section.from_readelf_line(l) for l in readelf_proc.stdout]
        sections = list(filter(None, sections))

        if readelf_proc.wait(3) != 0:
            raise subprocess.CalledProcessError(readelf_proc.returncode,
                                                readelf_proc.args)

        return sections
