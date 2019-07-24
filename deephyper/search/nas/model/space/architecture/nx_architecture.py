import networkx as nx
from collections.abc import Iterable

from deephyper.core.exceptions.nas.architecture import (InputShapeOfWrongType,
                                                  NodeAlreadyAdded,
                                                  StructureHasACycle,
                                                  WrongOutputShape,
                                                  WrongSequenceToSetOperations)
from deephyper.search.nas.model.space.node import (ConstantNode, Node,
                                                   VariableNode)


class NxArchitecture:
    """A NxArchitecture is an architecture based on a networkx graph.
    """

    def __init__(self, *args, **kwargs):
        self.graph = nx.DiGraph()

    def draw_graphviz(self, path):
        with open(path, 'w') as f:
            try:
                nx.nx_agraph.write_dot(self.graph, f)
            except:
                print('Error: can\'t create graphviz file...')

    def __len__(self):
        """Number of VariableNodes in the current architecture.

        Returns:
            int: number of variable nodes in the current architecture.
        """

        return len(self.nodes)

    @property
    def nodes(self):
        """Nodes of the current KArchitecture.

        Returns:
            iterator: nodes of the current KArchitecture.
        """

        return list(self.graph.nodes)

    def add_node(self, node):
        """Add a new node to the architecture.

        Args:
            node (Node): node to add to the architecture.

        Raises:
            TypeError: if 'node' is not an instance of Node.
            NodeAlreadyAdded: if 'node' has already been added to the architecture.
        """

        if not isinstance(node, Node):
            raise TypeError(f"'node' argument should be an instance of Node!")

        if node in self.nodes:
            raise NodeAlreadyAdded(node)

        self.graph.add_node(node)

    def connect(self, node1, node2):
        """Create a new connection in the KArchitecture graph.

        The edge created corresponds to : node1 -> node2.

        Args:
            node1 (Node)
            node2 (Node)

        Raise:
            StructureHasACycle: if the new edge is creating a cycle.
        """
        assert isinstance(node1, Node)
        assert isinstance(node2, Node)

        self.graph.add_edge(node1, node2)

        if not(nx.is_directed_acyclic_graph(self.graph)):
            raise StructureHasACycle(
                f'the connection between {node1} -> {node2} is creating a cycle in the architecture\'s graph.')

    @property
    def size(self):
        """Size of the search space define by the architecture
        """
        s = 0
        for n in filter(lambda n: isinstance(n, VariableNode), self.nodes):
            if n.num_ops != 0:
                if s == 0:
                    s = n.num_ops
                else:
                    s *= n.num_ops
        return s

    @property
    def max_num_ops(self):
        """Returns the maximum number of operations accross all VariableNodes of the struct.

        Returns:
            int: maximum number of Operations for a VariableNode in the current Structure.
        """
        return max(map(lambda n: n.num_ops, self.variable_nodes))

    @property
    def num_nodes(self):
        """Returns the number of VariableNodes in the current Structure.

        Returns:
            int: number of VariableNodes in the current Structure.
        """
        return len(list(self.variable_nodes))

    @property
    def variable_nodes(self):
        """Iterator of VariableNodes of the architecture.

        Returns:
            (Iterator(VariableNode)): generator of VariablesNodes of the architecture.
        """
        return filter(lambda n: isinstance(n, VariableNode), self.nodes)

    def denormalize(self, indexes):
        """Denormalize a sequence of normalized indexes to get a sequence of absolute indexes. Useful when you want to compare the number of different architectures.

        Args:
            indexes (Iterable): a sequence of normalized indexes.

        Returns:
            list: A list of absolute indexes corresponding to operations choosen with relative indexes of `indexes`.
        """
        assert isinstance(
            indexes, Iterable), 'Wrong argument, "indexes" should be of Iterable.'

        if len(indexes) != self.num_nodes:
            raise WrongSequenceToSetOperations(
                indexes, list(self.variable_nodes))

        return [vnode.denormalize(op_i) for op_i, vnode in zip(indexes, self.variable_nodes)]

    def get_output_nodes(self):
        """Get nodes of 'graph' without successors.

        Return:
            list: the nodes without successors of a DiGraph.
        """
        nodes = list(self.graph.nodes())
        output_nodes = []
        for n in nodes:
            if len(list(self.graph.successors(n))) == 0:
                output_nodes.append(n)
        return output_nodes

    @staticmethod
    def create_tensor_aux(g, n, train=None):
        """Recursive function to create the tensors from the graph.

        Args:
            g (nx.DiGraph): a graph
            n (nx.Node): a node
            train (bool): True if the network is built for training, False if the network is built for validation/testing (for example False will deactivate Dropout).

        Return:
            the tensor represented by n.
        """
        try:
            if n._tensor != None:
                output_tensor = n._tensor
            else:
                pred = list(g.predecessors(n))
                if len(pred) == 0:
                    output_tensor = n.create_tensor(train=train)
                else:
                    tensor_list = list()
                    for s_i in pred:
                        tmp = NxArchitecture.create_tensor_aux(
                            g, s_i, train=train)
                        if type(tmp) is list:
                            tensor_list.extend(tmp)
                        else:
                            tensor_list.append(tmp)
                    output_tensor = n.create_tensor(tensor_list, train=train)
            return output_tensor
        except TypeError:
            raise RuntimeError(f'Failed to build tensors from :{n}')
