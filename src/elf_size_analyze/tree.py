"""
The tree node class
"""

import itertools
import sys


class TreeNode:
    """
    Simple implementation of a tree with dynamic number of nodes.
    Provides a depth-first iterator. Someone could actually call this
    class TreeNode, as every object represents a single node.
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.children = []

    def add(self, children):
        if not isinstance(children, (list, tuple)):
            children = (children, )
        for child in children:
            self.children.append(child)
            child.parent = self

    def pre_order(self):
        """Iterator that yields tuples (node, depth). Depth-first, pre-order traversal."""
        return self.PreOrderIterator(self)

    def post_order(self):
        """Iterator that yields tuples (node, depth). Depth-first, post-order traversal."""
        return self.PostOrderIterator(self)

    def __iter__(self):
        for child in self.children:
            yield child

    class TreeIterator:
        def __init__(self, root, depth=0):
            self.root = root
            self.depth = depth

        def __iter__(self):
            raise NotImplementedError('Should yield pairs (node, depth)')

    # depth-first tree iterators
    class PreOrderIterator(TreeIterator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __iter__(self):
            yield self.root, self.depth
            children_iters = map(lambda child:
                                 self.__class__(child, self.depth + 1), self.root)
            for node in itertools.chain(*children_iters):
                yield node

    class PostOrderIterator(TreeIterator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __iter__(self):
            children_iters = map(lambda child:
                                 self.__class__(child, self.depth + 1), self.root)
            for node in itertools.chain(*children_iters):
                yield node
            yield self.root, self.depth


# only for testing the implementation
def test__TreeNode():
    class NameTree(TreeNode):
        def __init__(self, name, *args, **kwargs):
            self.name = name
            super().__init__(*args, **kwargs)

        def __repr__(self):
            return 'Node(%s)' % self.name

    def create_tree():
        root = NameTree('root')
        root.add([NameTree('n1'), NameTree('n2'), NameTree('n3')])
        root.children[0].add([NameTree('n1n1'), NameTree('n1n2'), NameTree('n1n3')])
        root.children[1].add([NameTree('n2n1'), NameTree('n2n2')])
        root.children[2].add([NameTree('n3n1')])
        root.children[2].children[0].add([NameTree('n3n1n1')])
        return root

    root = create_tree()
    print('\nIterate over a node (root node):')
    for node in root:
        print('    |%s' % node)

    methods = [TreeNode.pre_order, TreeNode.post_order]
    for method in methods:
        print('\nIterate over tree (%s):' % method.__name__)
        for node, depth in method(root):
            print('    |%s%-30s  parent=%s' % ('    ' * depth, node, node.parent))

    sys.exit(0)


#  test__TreeNode()