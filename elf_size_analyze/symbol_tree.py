"""
The symbol tree class
"""

import itertools
import logging
import math
import os
import pathlib

from elf_size_analyze.misc import sizeof_fmt
from elf_size_analyze.symbol import Symbol
from elf_size_analyze.tree_node import TreeNode

log = logging.getLogger('elf-size-analyze')

class SymbolsTreeByPath:
    """A tree built from symbols grouped by paths. Nodes can be symbols or paths."""

    class Node(TreeNode):
        def __init__(self, data, is_dir=False, *args, **kwargs):
            self.data = data
            self._is_dir = is_dir
            self.cumulative_size = None  # used for accumulating symbol sizes in paths
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
            return 'Node(%s)' % string

    def __init__(self, symbols=[]):
        self.tree_root = self.Node(None)
        self.orphans = self.Node('?')
        self.tree_root.add(self.orphans)
        for symbol in symbols:
            self.add(symbol)
        self.total_size = None

    def add(self, symbol):
        assert isinstance(symbol, Symbol), "Only instances of Symbol can be added!"
        if symbol.file is None:
            self.orphans.add(self.Node(symbol))
        else:
            if not os.path.isabs(symbol.file):
                log.warning('Symbol\'s path is not absolute: %s: %s'
                                % (symbol, symbol.file))
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
            path_child = list(filter(lambda node: node.data == part, path_children))
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
            path_key = lambda node: -node.cumulative_size if node.cumulative_size is not None else node.data
            ns1, ns2, ns3 = itertools.tee(non_symbols, 3)
            dirs = filter(self.Node.is_dir, ns1)
            files = filter(self.Node.is_file, ns2)
            others = filter(lambda n: not n.is_file() and not n.is_dir(), ns3)
            non_symbols = sorted(dirs, key=path_key) \
                + sorted(files, key=path_key) + list(others)
            symbols = sorted(symbols, key=lambda node: key(node.data), reverse=reverse)
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
            self.colors = colors or []  # avoid creating one list shared by all objects

        def print(self):
            if len(self.colors) > 0:
                print(sum(self.colors, Color()) + self.string + Color.RESET)
            else:
                print(self.string)

    def generate_printable_lines(self, *, max_width=80, min_size=0, header=None, indent=2,
                                 colors=True, alternating_colors=False, trim=True, human_readable=False):
        """
        Creates printable output in form of Protoline objects.
        Handles RIDICULLOUSLY complex printing. Someone could probably implement it easier.
        """
        # create and initially fill the lines
        protolines = self._generate_protolines(min_size)
        self._add_field_strings(protolines, indent, human_readable)
        # formatting string
        h_fmt = '{:{s0}}   {:{s1}}   {:{s2}}'
        fmt = '{:{s0}}   {:>{s1}}   {:>{s2}}'
        t_fmt = '{:{s0}}   {:>{s1}}   {:>{s2}}'
        table_headers = ('Symbol', 'Size', '%')
        # calculate sizes
        field_sizes = self._calculate_field_sizes(protolines, max_width=max_width,
                                                  initial=[len(h) for h in table_headers])
        # trim too long strings
        if trim:
            self._trim_strings(protolines, field_sizes)
        # prepare sizes dict
        sizes_dict = {'s%d' % i: s for i, s in enumerate(field_sizes)}
        # "render" the strings
        for line in protolines:
            if line.string is None:
                if len(line.field_strings) == 0:
                    line.string = ''
                else:
                    line.string = fmt.format(*line.field_strings, **sizes_dict)
        # preopare table header
        header_lines = self._create_header_protolines(h_fmt, table_headers, sizes_dict, header)
        for l in reversed(header_lines):
            protolines.insert(0, l)
        # prepare totals
        if self.total_size is not None:
            totals_lines = self._create_totals_protolines(t_fmt, sizes_dict, human_readable)
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
                raise Exception('Wrong symbol type encountered')
            elif node.is_symbol() and node.data.size < min_size:
                continue
            protolines.append(self.Protoline(depth, node))
        return protolines

    def _generate_node_dict(self, min_size):
        # generate dict of nodes
        nodeDict = dict()
        get_key = lambda node: node.data.name if node.is_symbol() else node.data

        for node, depth in self.tree_root.pre_order():
            if node.is_root():
                continue
            elif not (node.is_symbol() or node.is_path()):
                raise Exception('Wrong symbol type encountered')
            elif node.is_symbol() and node.data.size < min_size:
                continue

            nodePath = list()
            iterNode = node
            while iterNode.parent is not None:
                nodePath.append(iterNode)
                iterNode = iterNode.parent
            nodePath.reverse()

            children = nodeDict
            for n in nodePath[:-1]:
                children = children[get_key(n)]['children']

            key = get_key(node)
            children[key] = {
                'name': get_key(node),
                'cumulative_size': node.cumulative_size,
            }
            if not node.is_symbol():
                children[key]['children'] = {}

        return nodeDict

    def _add_field_strings(self, protolines, indent, human_readable):
        for line in protolines:
            indent_str = ' ' * indent * line.depth
            if line.node.is_path():
                size_str, percent_str = '-', '-'
                if line.node.cumulative_size is not None:
                    size_str = self._size_string(line.node.cumulative_size, human_readable)
                    if self.total_size is not None:
                        percent_str = '%.2f' % (line.node.cumulative_size / self.total_size * 100)
                fields = [indent_str + line.node.data, size_str, percent_str]
            elif line.node.is_symbol():
                percent_str = '-'
                if self.total_size is not None:
                    percent_str = '%.2f' % (line.node.data.size / self.total_size * 100)
                size_str = self._size_string(line.node.data.size, human_readable)
                fields = [indent_str + line.node.data.name, size_str, percent_str]
            else:
                raise Exception('Wrong symbol type encountered')
            line.field_strings = fields

    def _calculate_field_sizes(self, protolines, initial, max_width=0):
        field_sizes = initial
        for line in protolines:
            for i, s, in enumerate(line.field_strings):
                field_sizes[i] = max(len(s), field_sizes[i])
        # trim the fields if max_width is > 0
        if max_width > 0:
            if sum(field_sizes) > max_width:
                field_sizes[0] -= sum(field_sizes) - max_width
        return field_sizes

    def _trim_strings(self, protolines, field_sizes):
        for line in protolines:
            for i, s, in enumerate(line.field_strings):
                if len(s) > field_sizes[i]:
                    line.field_strings[i] = s[:field_sizes[i] - 3] + '...'

    def _create_header_protolines(self, header_fmt, table_headers, sizes_dict, header):
        table_header = header_fmt.format(*table_headers, **sizes_dict)
        separator = self._separator_string(len(table_header))
        if header is None:
            header = separator
        else:
            h = ' %s ' % header
            mid = len(separator) // 2
            before, after = int(math.ceil(len(h)/2)), int(math.floor(len(h)/2))
            header = separator[:mid - before] + h + separator[mid+after:]
        header_protolines = [self.Protoline(string=s) for s in [header, table_header, separator]]
        return header_protolines

    def _create_totals_protolines(self, fmt, sizes_dict, human_readable):
        totals = fmt.format('Symbols total', self._size_string(self.total_size, human_readable), '',
                            **sizes_dict)
        separator = self._separator_string(len(totals))
        return [self.Protoline(string=s) for s in [separator, totals, separator]]

    def _separator_string(self, length):
        return '=' * length

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
