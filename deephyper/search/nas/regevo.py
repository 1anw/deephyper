import os
import collections
import random
import numpy as np
import json

from deephyper.search import Search, util
from deephyper.core.logs.logging import JsonMessage as jm
from deephyper.evaluator.evaluate import Encoder

dhlogger = util.conf_logger(
    'deephyper.search.nas.regevo')

def key(d):
    return json.dumps(dict(arch_seq=d['arch_seq']), cls=Encoder)

class RegularizedEvolution(Search):
    """Regularized evolution.

    https://arxiv.org/abs/1802.01548

    Args:
        problem (str): Module path to the Problem instance you want to use for the search (e.g. deephyper.benchmark.nas.linearReg.Problem).
        run (str): Module path to the run function you want to use for the search (e.g. deephyper.search.nas.model.run.quick).
        evaluator (str): value in ['balsam', 'subprocess', 'processPool', 'threadPool'].
    """

    def __init__(self, problem, run, evaluator, population_size=100, sample_size=10, **kwargs):

        if evaluator == 'balsam':  # TODO: async is a kw
            balsam_launcher_nodes = int(
                os.environ.get('BALSAM_LAUNCHER_NODES', 1))
            deephyper_workers_per_node = int(
                os.environ.get('DEEPHYPER_WORKERS_PER_NODE', 1))
            n_free_nodes = balsam_launcher_nodes - 1  # Number of free nodes
            self.free_workers = n_free_nodes * \
                deephyper_workers_per_node  # Number of free workers
        else:
            self.free_workers = 1

        super().__init__(problem, run, evaluator, cache_key=key, **kwargs)

        dhlogger.info(jm(
            type='start_infos',
            alg='aging-evolution',
            nworkers=self.free_workers,
            encoded_space=json.dumps(self.problem.space, cls=Encoder)
            ))

        # Setup
        self.pb_dict = self.problem.space
        cs_kwargs = self.pb_dict['create_structure'].get('kwargs')
        if cs_kwargs is None:
            architecture = self.pb_dict['create_structure']['func']()
        else:
            architecture = self.pb_dict['create_structure']['func'](**cs_kwargs)

        self.space_list = [(0, vnode.num_ops-1) for vnode in architecture.variable_nodes]
        self.population_size = population_size
        self.sample_size = sample_size

    @staticmethod
    def _extend_parser(parser):
        parser.add_argument("--problem",
                            default="deephyper.benchmark.nas.linearReg.Problem",
                            help="Module path to the Problem instance you want to use for the search (e.g. deephyper.benchmark.nas.linearReg.Problem)."
                            )
        parser.add_argument("--run",
                            default="deephyper.search.nas.model.run.alpha.run",
                            help="Module path to the run function you want to use for the search (e.g. deephyper.search.nas.model.run.alpha.run)."
                            )
        parser.add_argument("--max-evals", type=int, default=1e10,
                            help="maximum number of evaluations.")
        parser.add_argument("--population-size", type=int, default=100,
                            help="the number of individuals to keep in the population.")
        # parser.add_argument("--cycles", type=int, default=1e10,
        #                     hel='the number of cycles the algorithm should run for.')
        parser.add_argument("--sample-size", type=int, default=10,
                            help="the number of individuals that should participate in each tournament.")
        return parser

    def main(self):

        num_evals_done = 0
        # num_cyles_done = 0
        population = collections.deque(maxlen=self.population_size)

        # Filling available nodes at start
        self.evaluator.add_eval_batch(self.gen_random_batch(size=self.free_workers))


        # Main loop
        while num_evals_done < self.max_evals:

            # Collecting finished evaluations
            new_results = list(self.evaluator.get_finished_evals())


            if len(new_results) > 0:
                population.extend(new_results)
                stats = {
                    'num_cache_used': self.evaluator.stats['num_cache_used'],
                }
                dhlogger.info(jm(type='env_stats', **stats))
                self.evaluator.dump_evals(saved_key='arch_seq')

                num_received = len(new_results)
                num_evals_done += num_received

                # If the population is big enough evolve the population
                if len(population) == self.population_size:
                    children_batch = []
                    # For each new parent/result we create a child from it
                    for _ in range(len(new_results)):
                        # select_sample
                        indexes = np.random.choice(self.population_size, self.sample_size, replace=False)
                        sample = [population[i] for i in indexes]
                        # select_parent
                        parent = self.select_parent(sample)
                        # copy_mutate_parent
                        child = self.copy_mutate_arch(parent)
                        # add child to batch
                        children_batch.append(child)
                    # submit_childs
                    if len(new_results) > 0:
                        self.evaluator.add_eval_batch(children_batch)
                else: # If the population is too small keep increasing it
                    self.evaluator.add_eval_batch(self.gen_random_batch(size=len(new_results)))

    def select_parent(self, sample: list) -> list:
        cfg, _ = max(sample, key=lambda x: x[1])
        return cfg['arch_seq']

    def gen_random_batch(self, size: int) -> list:
        batch = []
        for _ in range(size):
            cfg = self.pb_dict.copy()
            cfg['arch_seq'] = self.random_architecture()
            batch.append(cfg)
        return batch

    def random_architecture(self) -> list:
        return [np.random.choice(b+1) for (_,b) in self.space_list]

    def copy_mutate_arch(self, parent_arch: list) -> dict:
        """
        # ! Time performance is critical because called sequentialy

        Args:
            parent_arch (list(int)): [description]

        Returns:
            dict: [description]

        """
        i = np.random.choice(len(parent_arch))
        child_arch = parent_arch[:]

        range_upper_bound = self.space_list[i][1]
        elements = [j for j in range(range_upper_bound+1) if j != child_arch[i]]

        # The mutation has to create a different architecture!
        sample = np.random.choice(elements, 1)[0]

        child_arch[i] = sample
        cfg = self.pb_dict.copy()
        cfg['arch_seq'] = child_arch
        return cfg


if __name__ == "__main__":
    args = RegularizedEvolution.parse_args()
    search = RegularizedEvolution(**vars(args))
    search.main()
