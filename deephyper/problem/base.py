import inspect
from collections import OrderedDict
from inspect import signature
from pprint import pformat

import ConfigSpace as cs
import ConfigSpace.hyperparameters as csh
import numpy as np

from deephyper.core.exceptions.problem import *


def check_hyperparameter(parameter, name=None):
    if isinstance(parameter, csh.Hyperparameter):
        return parameter

    if not isinstance(parameter, (list, tuple, np.ndarray, float, int)):
        raise ValueError(
            "Shortcut definition of an hyper-parameter has to be a list, tuple, array, float or int."
        )

    assert type(name) is str, f"Parameter of value {parameter} is not named!"

    if isinstance(parameter, (int, float)):  # Constant parameter
        return csh.Constant(name, parameter)

    if any([isinstance(p, (str, bool)) or isinstance(p, np.bool_) for p in parameter]):
        return csh.CategoricalHyperparameter(name, choices=parameter)

    if len(parameter) == 2:
        if all([isinstance(p, int) for p in parameter]):
            return csh.UniformIntegerHyperparameter(
                name=name, lower=parameter[0], upper=parameter[1], log=False
            )
        elif any([isinstance(p, float) for p in parameter]):
            return csh.UniformFloatHyperparameter(
                name, lower=parameter[0], upper=parameter[1], log=False
            )
        else:
            raise ValueError(
                f"Invalid dimension {name}: {parameter}. Read the documentation for"
                f" supported types."
            )

    raise ValueError(
        f"Invalid dimension {name}: {parameter}. Read the documentation for"
        f" supported types."
    )


class BaseProblem:
    """Representation of a problem.
    """

    def __init__(self, seed=None):
        self.seed = seed
        self._space = cs.ConfigurationSpace(seed=seed)
        self.references = []  # starting points

    def __str__(self):
        return repr(self)

    def __repr__(self):
        prob = repr(self._space)
        if len(self.references) == 0:
            return prob
        else:
            start_points = (
                f"{pformat({k:v for k,v in enumerate(self.starting_point_asdict)})}"
            )
            return prob + "\n\nStarting Point\n" + start_points

    def add_dim(self, p_name=None, p_space=None):
        """Deprecated! Add a dimension to the search space.

        Args:
            p_name (str): name of the parameter/dimension.
            p_space (Object): space corresponding to the new dimension.
        """

        csh_parameter = check_hyperparameter(p_space, p_name)
        self._space.add_hyperparameter(csh_parameter)

    def add_hyperparameter(self, value, name=None):
        csh_parameter = check_hyperparameter(value, name)
        self._space.add_hyperparameter(csh_parameter)

    @property
    def space(self):
        return self._space

    def add_starting_point(self, **parameters):
        config = cs.Configuration(self._space, parameters)
        self._space.check_configuration(config)
        self.references.append([parameters[p_name] for p_name in self._space])

    @property
    def starting_point(self):
        """Starting point(s) of the search space.

        Returns:
            list(list): list of starting points where each point is a list of values. Values are indexed in the same order as the order of creation of space's dimensions.
        """
        return self.references

    @property
    def starting_point_asdict(self):
        """Starting point(s) of the search space.

        Returns:
            list(dict): list of starting points where each point is a dict of values. Each key are correspnding to dimensions of the space.
        """
        return [{k: v for k, v in zip(list(self._space), p)} for p in self.references]


def test_base_problem():
    import ConfigSpace.hyperparameters as CSH

    alpha = CSH.UniformFloatHyperparameter(name="alpha", lower=0, upper=1)
    beta = CSH.UniformFloatHyperparameter(name="beta", lower=0, upper=1)

    pb = BaseProblem(42)
    pb.add_hyperparameter(alpha)
    pb.add_hyperparameter(beta)
    pb.add_

    print(pb)
    # point = pb.space.sample_configuration()
    # for e, v in dict(point).items():
    #     print(e, v)
    # #for e in pb.space:
    # #   print(e)


if __name__ == "__main__":
    test_base_problem()
