"""Definition of a symbol"""

import os
import re
import math
import logging
import pathlib
import itertools
import subprocess

from elf_size_analyze.misc.color import Color
from elf_size_analyze.misc.helpers import g, sizeof_fmt
from elf_size_analyze.misc.tree_node import TreeNode

from ndicts.ndicts import NestedDict
from mergedeep import merge

log = logging.getLogger("elfSizeAnalyze")


class Symbol:
    """
    Represents a linker symbol in an ELF file. Attributes are as in the output
    of readelf command. Additionally, has optional file path and line number.
    """

    def __init__(
        self,
        num,
        name,
        value,
        size,
        type,
        bind,
        visibility,
        section,
        file=None,
        line=None,
    ):
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
        return "Symbol(%s)" % (self.name,)

    # Regex for parsing readelf output lines
    # Readelf output should look like the following:
    #   Symbol table '.symtab' contains 623 entries:
    #      Num:    Value  Size Type    Bind   Vis      Ndx Name
    #        0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND
    #   ...
    #      565: 08002bf9     2 FUNC    WEAK   DEFAULT    2 TIM2_IRQHandler
    #      566: 200002a8    88 OBJECT  GLOBAL DEFAULT    8 hspi1
    pattern_fields = [
        r"\s*",
        g("num", r"\d+"),
        r":",
        r"\s+",
        g("value", r"[0-9a-fA-F]+"),
        r"\s+",
        g("size", r"(0x)?[0-9A-Fa-f][0-9A-Fa-f]*"),  # accept dec & hex numbers
        r"\s+",
        g("type", r"\S+"),
        r"\s+",
        g("bind", r"\S+"),
        r"\s+",
        g("visibility", r"\S+"),
        r"\s+",
        g("section", r"\S+"),
        r"\s+",
        g("name", r".*"),
    ]
    pattern = r"^{}$".format(r"".join(pattern_fields))
    pattern = re.compile(pattern)

    @classmethod
    def from_readelf_line(
        cls,
        line,
        ignored_types=["NOTYPE", "SECTION", "FILE"],
        ignore_zero_size=True,
    ):
        """
        Create a Symbol from a line of `readelf -Ws` output.
        """
        m = cls.pattern.match(line)
        if not m:
            log.debug("no match: " + line.strip())
            return None

        # convert non-string values
        m = m.groupdict()
        m["num"] = int(m["num"])
        m["value"] = int(m["value"], 16)
        m["size"] = (
            int(m["size"]) if m["size"].isdecimal() else int(m["size"], 16)
        )
        try:  # for numeric sections
            m["section"] = int(m["section"])
        except ValueError:
            pass

        # ignore if needed
        if (
            not m["name"].strip()
            or m["type"].lower() in map(str.lower, ignored_types)
            or (ignore_zero_size and m["size"] == 0)
        ):
            log.debug("ignoring: " + line.strip())
            return None

        # create the Symbol
        s = Symbol(**m)

        return s

    @classmethod
    def extract_elf_symbols_info(cls, elf_file, readelf_exe="readelf"):
        """
        Uses binutils 'readelf' to find info about all symbols from an ELF file.
        """
        flags = ["--wide", "--syms"]
        readelf_proc = subprocess.Popen(
            [readelf_exe, *flags, elf_file],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )

        # parse lines
        log.info("Using readelf symbols regex: %s" % cls.pattern.pattern)
        symbols = [
            Symbol.from_readelf_line(line) for line in readelf_proc.stdout
        ]
        n_ignored = len(list(filter(lambda x: x is None, symbols)))
        symbols = list(filter(None, symbols))

        if readelf_proc.wait(3) != 0:
            raise subprocess.CalledProcessError(
                readelf_proc.returncode, readelf_proc.args
            )

        log.info(
            "ignored %d/%d symbols" % (n_ignored, len(symbols) + n_ignored)
        )

        return symbols


class SymbolsTreeByPath:
    """A tree built from symbols grouped by paths. Nodes can be symbols or paths."""

    class Node(TreeNode):
        def __init__(self, data, is_dir=False, *args, **kwargs):
            self.data = data
            self._is_dir = is_dir
            self.cumulative_size = (
                None  # used for accumulating symbol sizes in paths
            )
            super().__init__(*args, **kwargs)

        def is_symbol(self):
            return isinstance(self.data, Symbol)

        def is_root(self):
            return self.data is None

        def is_path(self):
            return not self.is_root() and not self.is_symbol()

        def is_dir(self):
            return self.is_path() and self._is_dir

        def is_file(self):
            return self.is_path() and not self._is_dir

        def __repr__(self):
            string = self.data.name if self.is_symbol() else self.data
            return "Node(%s)" % string

    def __init__(self, symbols=[]):
        self.tree_root = self.Node(None)
        self.orphans = self.Node("?")
        self.tree_root.add(self.orphans)
        for symbol in symbols:
            self.add(symbol)
        self.total_size = None

    def add(self, symbol):
        assert isinstance(
            symbol, Symbol
        ), "Only instances of Symbol can be added!"
        if symbol.file is None:
            self.orphans.add(self.Node(symbol))
        else:
            if not os.path.isabs(symbol.file):
                log.warning(
                    "Symbol's path is not absolute: %s: %s"
                    % (symbol, symbol.file)
                )
            self._add_symbol_with_path(symbol)

    def _add_symbol_with_path(self, symbol):
        """
        Adds the given symbol by creating nodes for each path component
        before adding symbol as the last ("leaf") node.
        """
        path = pathlib.Path(symbol.file)
        node = self.tree_root
        for part in path.parts:
            # find it the part exists in children
            path_children = filter(self.Node.is_path, node.children)
            path_child = list(
                filter(lambda node: node.data == part, path_children)
            )
            assert len(path_child) <= 1
            # if it does not exsits, then create it and add
            if len(path_child) == 0:
                path_child = self.Node(part, is_dir=True)
                node.add(path_child)
            else:
                path_child = path_child[0]
            # go 'into' this path part's node
            node = path_child
        # remove directory signature from last path part
        node._is_dir = False
        # last, add the symbol, the "tree leaf"
        node.add(self.Node(symbol))

    def merge_paths(self, fish_like=False):
        """Merges all path componenets that have only one child into single nodes."""
        for node, depth in self.tree_root.pre_order():
            # we want only path nodes that have only one path node
            if node.is_path() and len(node.children) == 1:
                child = node.children[0]
                if child.is_path():
                    # add this node's path to its child
                    this_path = node.data
                    if fish_like:
                        head, tail = os.path.split(this_path)
                        this_path = os.path.join(head, tail[:1])
                    child.data = os.path.join(this_path, child.data)
                    # remove this node and reparent its child
                    node.parent.children.remove(node)
                    node.parent.add(child)

    def sort(self, key, reverse=False):
        """
        Sort all symbol lists by the given key - function that takes a Symbol as an argument.
        sort_paths_by_name - if specified, then paths are sorted by name (directories first).
        reverse - applies to symbols
        reverse_paths - appliesto paths (still, directories go first)
        """
        # to avoid sorting the same list many times, gather them first
        nodes_with_children = []
        for node, depth in self.tree_root.pre_order():
            if len(node.children) > 1:
                nodes_with_children.append(node)
        for node in nodes_with_children:
            # we need tee to split generators into many so that filter will work as expected
            ch1, ch2 = itertools.tee(node.children)
            symbols = filter(self.Node.is_symbol, ch1)
            non_symbols = filter(lambda n: not n.is_symbol(), ch2)
            # sort others by size if available else by name, directories first
            # add - to size, as we need reverse sorting for path names

            def path_key(node):
                return (
                    -node.cumulative_size
                    if node.cumulative_size is not None
                    else node.data
                )

            ns1, ns2, ns3 = itertools.tee(non_symbols, 3)
            dirs = filter(self.Node.is_dir, ns1)
            files = filter(self.Node.is_file, ns2)
            others = filter(lambda n: not n.is_file() and not n.is_dir(), ns3)
            non_symbols = (
                sorted(dirs, key=path_key)
                + sorted(files, key=path_key)
                + list(others)
            )
            symbols = sorted(
                symbols, key=lambda node: key(node.data), reverse=reverse
            )
            children = list(non_symbols) + list(symbols)
            node.children = children

    def accumulate_sizes(self, reset=True):
        """
        Traverse tree bottom-up to accumulate symbol sizes in paths.
        """
        if reset:
            for node, depth in self.tree_root.pre_order():
                node.cumulative_size = None
            # Avoid errors when there are no orphans but the root Node('?')
            self.orphans.cumulative_size = 0
        for node, depth in self.tree_root.post_order():
            if node.parent is None:
                continue
            if node.parent.cumulative_size is None:
                node.parent.cumulative_size = 0
            if node.is_symbol():
                node.cumulative_size = node.data.size
            node.parent.cumulative_size += node.cumulative_size

    def calculate_total_size(self):
        # calculate the total size
        all_nodes = (node for node, _ in self.tree_root.pre_order())
        all_symbols = filter(self.Node.is_symbol, all_nodes)
        self.total_size = sum(s.data.size for s in all_symbols)

    class Protoline:
        def __init__(self, depth=0, node=None, string=None, colors=None):
            self.depth = depth
            self.node = node
            self.string = string
            self.field_strings = []
            self.colors = (
                colors or []
            )  # avoid creating one list shared by all objects

        def print(self):
            if len(self.colors) > 0:
                print(sum(self.colors, Color()) + self.string + Color.RESET)
            else:
                print(self.string)

    def generate_printable_lines(
        self,
        *,
        max_width=80,
        min_size=0,
        header=None,
        indent=2,
        colors=True,
        alternating_colors=False,
        trim=True,
        human_readable=False
    ):
        """
        Creates printable output in form of Protoline objects.
        Handles RIDICULLOUSLY complex printing. Someone could probably implement it easier.
        """
        # create and initially fill the lines
        protolines = self._generate_protolines(min_size)
        self._add_field_strings(protolines, indent, human_readable)
        # formatting string
        h_fmt = "{:{s0}}   {:{s1}}   {:{s2}}"
        fmt = "{:{s0}}   {:>{s1}}   {:>{s2}}"
        t_fmt = "{:{s0}}   {:>{s1}}   {:>{s2}}"
        table_headers = ("Symbol", "Size", "%")
        # calculate sizes
        field_sizes = self._calculate_field_sizes(
            protolines,
            max_width=max_width,
            initial=[len(h) for h in table_headers],
        )
        # trim too long strings
        if trim:
            self._trim_strings(protolines, field_sizes)
        # prepare sizes dict
        sizes_dict = {"s%d" % i: s for i, s in enumerate(field_sizes)}
        # "render" the strings
        for line in protolines:
            if line.string is None:
                if len(line.field_strings) == 0:
                    line.string = ""
                else:
                    line.string = fmt.format(*line.field_strings, **sizes_dict)
        # preopare table header
        header_lines = self._create_header_protolines(
            h_fmt, table_headers, sizes_dict, header
        )
        for line in reversed(header_lines):
            protolines.insert(0, line)
        # prepare totals
        if self.total_size is not None:
            totals_lines = self._create_totals_protolines(
                t_fmt, sizes_dict, human_readable
            )
            protolines.extend(totals_lines)
        # add colors
        if colors:
            self._add_colors(protolines, alternating_colors)
        return protolines

    def _generate_protolines(self, min_size):
        # generate list of nodes with indent to be printed
        protolines = []
        for node, depth in self.tree_root.pre_order():
            # we never print root so subtract its depth
            depth = depth - 1
            if node.is_root():
                continue
            elif not (node.is_symbol() or node.is_path()):
                raise Exception("Wrong symbol type encountered")
            elif node.is_symbol() and node.data.size < min_size:
                continue
            protolines.append(self.Protoline(depth, node))
        return protolines

    def _generate_node_dict(self, min_size):
        # generate dict of nodes
        nodeDict = dict()
        for node, depth in self.tree_root.pre_order():
            nd = NestedDict()
            if node.is_root():
                continue
            elif not (node.is_symbol() or node.is_path()):
                raise Exception("Wrong symbol type encountered")
            elif node.is_symbol() and node.data.size < min_size:
                continue
            nodePath = list()
            iterNode = node
            nodePath.insert(
                0,
                iterNode.data.name if iterNode.is_symbol() else iterNode.data,
            )
            while iterNode.parent.data is not None:
                nodePath.insert(0, "children")
                nodePath.insert(
                    0,
                    iterNode.parent.data.name
                    if iterNode.parent.is_symbol()
                    else iterNode.parent.data,
                )
                iterNode = iterNode.parent

            nd[tuple(nodePath) + ("name",)] = (
                node.data.name if node.is_symbol() else node.data
            )
            nd[tuple(nodePath) + ("cumulative_size",)] = node.cumulative_size
            merge(nodeDict, nd.to_dict())

        return nodeDict

    def _add_field_strings(self, protolines, indent, human_readable):
        for line in protolines:
            indent_str = " " * indent * line.depth
            if line.node.is_path():
                size_str, percent_str = "-", "-"
                if line.node.cumulative_size is not None:
                    size_str = self._size_string(
                        line.node.cumulative_size, human_readable
                    )
                    if self.total_size is not None:
                        percent_str = "%.2f" % (
                            line.node.cumulative_size / self.total_size * 100
                        )
                fields = [indent_str + line.node.data, size_str, percent_str]
            elif line.node.is_symbol():
                percent_str = "-"
                if self.total_size is not None:
                    percent_str = "%.2f" % (
                        line.node.data.size / self.total_size * 100
                    )
                size_str = self._size_string(
                    line.node.data.size, human_readable
                )
                fields = [
                    indent_str + line.node.data.name,
                    size_str,
                    percent_str,
                ]
            else:
                raise Exception("Wrong symbol type encountered")
            line.field_strings = fields

    def _calculate_field_sizes(self, protolines, initial, max_width=0):
        field_sizes = initial
        for line in protolines:
            for (
                i,
                s,
            ) in enumerate(line.field_strings):
                field_sizes[i] = max(len(s), field_sizes[i])
        # trim the fields if max_width is > 0
        if max_width > 0:
            if sum(field_sizes) > max_width:
                field_sizes[0] -= sum(field_sizes) - max_width
        return field_sizes

    def _trim_strings(self, protolines, field_sizes):
        for line in protolines:
            for (
                i,
                s,
            ) in enumerate(line.field_strings):
                if len(s) > field_sizes[i]:
                    line.field_strings[i] = s[: field_sizes[i] - 3] + "..."

    def _create_header_protolines(
        self, header_fmt, table_headers, sizes_dict, header
    ):
        table_header = header_fmt.format(*table_headers, **sizes_dict)
        separator = self._separator_string(len(table_header))
        if header is None:
            header = separator
        else:
            h = " %s " % header
            mid = len(separator) // 2
            before, after = int(math.ceil(len(h) / 2)), int(
                math.floor(len(h) / 2)
            )
            header = separator[: mid - before] + h + separator[mid + after:]
        header_protolines = [
            self.Protoline(string=s) for s in [header, table_header, separator]
        ]
        return header_protolines

    def _create_totals_protolines(self, fmt, sizes_dict, human_readable):
        totals = fmt.format(
            "Symbols total",
            self._size_string(self.total_size, human_readable),
            "",
            **sizes_dict
        )
        separator = self._separator_string(len(totals))
        return [
            self.Protoline(string=s) for s in [separator, totals, separator]
        ]

    def _separator_string(self, length):
        return "=" * length

    def _add_colors(self, protolines, alternating_colors):
        second_symbol_color = False
        for line in protolines:
            c = []
            if line.node is None:  # header lines
                c = [Color.BOLD, Color.BLUE]
            elif line.node.is_file():
                c = [Color.L_BLUE]
            elif line.node.is_dir():
                c = [Color.BLUE]
            elif line.node.is_symbol():
                if second_symbol_color and alternating_colors:
                    c = [Color.L_GREEN]
                    second_symbol_color = False
                else:
                    c = [Color.L_YELLOW]
                    second_symbol_color = True
            line.colors += c

    def _size_string(self, size, human_readable):
        if human_readable:
            return sizeof_fmt(size)
        return str(size)


def extract_elf_symbols_fileinfo(elf_file, nm_exe="nm"):
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
    pattern_fields = [
        g("name", r"\S+"),
        r"\s+",
        g("type", r"\S+"),
        r"\s+",
        g("value", r"[0-9a-fA-F]+"),
        r"\s+",
        g("size", r"[0-9a-fA-F]+"),
        g("fileinfo", r".*"),
    ]
    pattern = r"^{}$".format(r"".join(pattern_fields))
    pattern = re.compile(pattern)
    log.info("Using nm symbols regex: %s" % pattern.pattern)

    # use posix format
    flags = ["--portability", "--line-numbers"]
    nm_proc = subprocess.Popen(
        [nm_exe, *flags, elf_file],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )

    # process nm output
    fileinfo_dict = {}
    for line in nm_proc.stdout:
        m = pattern.match(line)
        if not m:
            continue

        # parse the file info
        file, line = None, None
        fileinfo = m.group("fileinfo").strip()
        if len(fileinfo) > 0:
            # check for line number
            line_i = fileinfo.rfind(":")
            if line_i >= 0:
                file = fileinfo[:line_i]
                line = int(fileinfo[line_i + 1])
            else:
                file = fileinfo
            # try to make the path more readable
            file = os.path.normpath(file)

        fileinfo_dict[m.group("name")] = file, line

    if nm_proc.wait(3) != 0:
        raise subprocess.CalledProcessError(nm_proc.returncode, nm_proc.args)

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
            log.warning(
                'nm found fileinfo for symbol "%s", which has not been found by readelf'
                % symbol_name
            )


def demangle_symbol_names(symbols, cppfilt_exe="c++filt"):
    """
    Use c++filt to demangle symbol names in-place.
    """
    flags = []
    cppfilt_proc = subprocess.Popen(
        [cppfilt_exe, *flags],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )

    for symbol in symbols:
        # write the line and flush it
        # not super-efficient but writing all at once for large list of symbols
        # can block the program (probably due to buffering)
        cppfilt_proc.stdin.write((symbol.name + "   \n"))
        cppfilt_proc.stdin.flush()
        new_name = cppfilt_proc.stdout.readline().strip()
        symbol.name = new_name
    cppfilt_proc.stdin.close()

    if cppfilt_proc.wait(3) != 0:
        raise subprocess.CalledProcessError(
            cppfilt_proc.returncode, cppfilt_proc.args
        )
