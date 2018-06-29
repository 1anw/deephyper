from pprint import pprint
import deephyper.model.arch as a
from deephyper.benchmarks.mnistNas.load_data import load_data
from deephyper.model.trainer.tf import BasicTrainer
from deephyper.model.builder.tf import BasicBuilder
from pprint import pprint


def run(param_dict):
    config = param_dict
    pprint(config, indent=4)


    # Loading data
    (t_X, t_y), (v_X, v_y) = load_data(dest='MNISTnas')
    config[a.data] = { a.train_X: t_X,
                            a.train_Y: t_y,
                            a.valid_X: v_X,
                            a.valid_Y: v_y }


    # For all the Net generated by the CONTROLLER
    pprint(config)
    trainer = BasicTrainer(config)

    arch_def = config['arch_def']
    pprint(arch_def)
    global_step = config['global_step']

    # Run the trainer and get the rewards
    rewards = trainer.get_rewards(arch_def, global_step)
    print('OUTPUT: ', rewards)
    return rewards
