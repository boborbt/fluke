from copy import deepcopy
import numpy as np
import torch
import glob
import torch.nn as nn

from algorithms.fedavg import FedAVG
from algorithms.fedsgd import FedSGD
from algorithms.scaffold import SCAFFOLD, ScaffoldOptimizer
from algorithms.fedprox import FedProx
from algorithms.flhalf import FLHalf
from fl_bench.algorithms.fedbn import FedBN
from fl_bench.algorithms.fedopt import FedOpt, FedOptMode

from fl_bench import GlobalSettings
from fl_bench.data import DataSplitter, Distribution, FastTensorDataLoader, DATASET_MAP, IIDNESS_MAP
from fl_bench.utils import plot_comparison
from fl_bench.net import *
from utils import OptimizerConfigurator, Log, set_seed
from evaluation import ClassificationEval

from rich.pretty import pprint
import typer
app = typer.Typer()

GlobalSettings().auto_device()
DEVICE = GlobalSettings().get_device()


N_CLIENTS = 5
N_ROUNDS = 100
N_EPOCHS = 5
BATCH_SIZE = 225
ELIGIBILITY_PERCENTAGE = .5


@app.command()
def run(algorithm: str = typer.Argument(..., help='Algorithm to run'),
        dataset: str = typer.Argument(..., help='Dataset'),
        n_clients: int = typer.Option(N_CLIENTS, help='Number of clients'),
        n_rounds: int = typer.Option(N_ROUNDS, help='Number of rounds'),
        n_epochs: int = typer.Option(N_EPOCHS, help='Number of epochs'),
        batch_size: int = typer.Option(BATCH_SIZE, help='Batch size'),
        elegibility_percentage: float = typer.Option(ELIGIBILITY_PERCENTAGE, help='Elegibility percentage'),
        distribution: int = typer.Option(Distribution.IID.value, help='Data distribution'),
        seed: int = typer.Option(987654, help='Seed')):
    
    assert algorithm in ['fedavg', 'fedprox', 'flhalf', 'scaffold', 'fedbn', 'fedopt', 'fedsgd'], "Algorithm not supported"
    assert dataset in DATASET_MAP.keys(), "Dataset not supported"

    set_seed(seed)

    print("Running configuration:")
    options = deepcopy(locals())
    options["distribution"] = Distribution(options["distribution"]).name
    pprint(options, expand_all=True)
    print()

    MODEL = MLP().to(DEVICE)

    train_data, test_data = DATASET_MAP[dataset]()

    data_splitter = DataSplitter(train_data.data / 255., 
                                 train_data.targets, 
                                 n_clients=n_clients, 
                                 distribution=Distribution(distribution), 
                                 batch_size=batch_size,
                                 seed=seed)

    test_loader = FastTensorDataLoader(test_data.data / 255., 
                                       test_data.targets, 
                                       batch_size=100, 
                                       shuffle=False)

    logger = Log(ClassificationEval(test_loader, nn.CrossEntropyLoss()))

    if algorithm == 'fedavg':
        fl_algo = FedAVG(n_clients=n_clients,
                           n_rounds=n_rounds, 
                           n_epochs=n_epochs, 
                           model=MODEL, 
                           optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.01), 
                           loss_fn=nn.CrossEntropyLoss(), 
                           elegibility_percentage=elegibility_percentage,
                           seed=seed)
        fl_algo.init_parties(data_splitter, logger)
    
    elif algorithm == 'fedsgd':
        fl_algo = FedSGD(n_clients=n_clients,
                           n_rounds=n_rounds, 
                           model=MODEL, 
                           optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.1), 
                           loss_fn=nn.CrossEntropyLoss(), 
                           elegibility_percentage=elegibility_percentage,
                           seed=seed)
        fl_algo.init_parties(data_splitter, logger)
    
    elif algorithm == 'fedbn':
        fl_algo = FedBN(n_clients=n_clients,
                           n_rounds=n_rounds, 
                           n_epochs=n_epochs, 
                           model=MODEL, 
                           optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.01), 
                           loss_fn=nn.CrossEntropyLoss(), 
                           elegibility_percentage=elegibility_percentage,
                           seed=seed)
        fl_algo.init_parties(data_splitter, logger)

    elif algorithm == 'fedprox':
        fl_algo = FedProx(n_clients=n_clients,
                            n_rounds=n_rounds, 
                            n_epochs=n_epochs, 
                            client_mu = 0.1,
                            model=MODEL, 
                            optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.01), 
                            loss_fn=nn.CrossEntropyLoss(), 
                            elegibility_percentage=elegibility_percentage,
                            seed=seed)
        fl_algo.init_parties(data_splitter, logger)

    elif algorithm == 'scaffold':
        fl_algo = SCAFFOLD(n_clients=n_clients,
                             n_rounds=n_rounds, 
                             n_epochs=n_epochs, 
                             model=MODEL, 
                             optimizer_cfg=OptimizerConfigurator(ScaffoldOptimizer, lr=0.01), 
                             loss_fn=nn.CrossEntropyLoss(), 
                             elegibility_percentage=elegibility_percentage,
                             seed=seed)
        fl_algo.init_parties(data_splitter, global_step=1, callback=logger)
    
    elif algorithm == 'fedopt':
        fl_algo = FedOpt(n_clients=n_clients,
                         n_rounds=n_rounds, 
                         n_epochs=n_epochs, 
                         mode=FedOptMode.FedYogi,
                         server_lr=0.01,
                         beta1=0.9,
                         beta2=0.99,
                         tau=0.0001,                           
                         model=MODEL, 
                         optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.01), 
                         loss_fn=nn.CrossEntropyLoss(), 
                         elegibility_percentage=elegibility_percentage,
                         seed=seed)
        fl_algo.init_parties(data_splitter, logger)

    elif algorithm == 'flhalf':
        fl_algo = FLHalf(n_clients=n_clients,
                         n_rounds=n_rounds, 
                         client_n_epochs=n_epochs, 
                         server_n_epochs=2,
                         server_batch_size=batch_size, 
                         model=MODEL, 
                         server_optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.01), 
                         client_optimizer_cfg=OptimizerConfigurator(torch.optim.SGD, lr=0.05), 
                         loss_fn=nn.CrossEntropyLoss(), 
                         private_layers=["fc1", "bn1"],
                         elegibility_percentage=elegibility_percentage,
                         seed=seed)
        fl_algo.init_parties(data_splitter, logger)
    
    else:
        raise ValueError(f'Algorithm {algorithm} not supported')
    
    fl_algo.run(10)
    logger.save(f'./log/{fl_algo}_{dataset}_{IIDNESS_MAP[Distribution(distribution)]}.json')


@app.command()
def compare(dataset: str=typer.Option('mnist', help='Dataset'),
            n_clients: int=typer.Option(100, help='Number of clients'),
            distribution: int=typer.Option(Distribution.IID.value, help='Data distribution'),
            show_loss: bool=typer.Option(True, help='Show loss graph')):

    paths = glob.glob(f'./log/*C={n_clients}*_{dataset}_{IIDNESS_MAP[Distribution(distribution)]}.json')
    plot_comparison(*paths, show_loss=show_loss)

# compare('./log/flhalf_noniid_dir.json', './log/fedavg_noniid_dir.json', show_loss=True) 


if __name__ == '__main__':
    app()