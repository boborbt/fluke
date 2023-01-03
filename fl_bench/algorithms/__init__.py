from abc import ABC
from typing import Callable

from torch.nn import Module

from client import Client
from server import Server

from fl_bench.data import DataSplitter
from fl_bench.utils import OptimizerConfigurator

class FLEnvironment(ABC):

    def init_parties(self, callback: Callable=None, **kwargs):
        raise NotImplementedError

    def run(self, *args, **kwargs):
        raise NotImplementedError


class CentralizedFL(FLEnvironment):
    def __init__(self,
                 n_clients: int,
                 n_rounds: int, 
                 n_epochs: int,
                 model: Module, 
                 optimizer_cfg: OptimizerConfigurator, 
                 loss_fn: Callable,
                 elegibility_percentage: float=0.5,
                 seed: int=42):
        
        self.n_clients = n_clients
        self.n_rounds = n_rounds
        self.n_epochs = n_epochs
        self.seed = seed
        self.model = model
        self.optimizer_cfg = optimizer_cfg
        self.elegibility_percentage = elegibility_percentage
        self.loss_fn = loss_fn
        self.data_assignment = None
    
    def init_parties(self, data_splitter: DataSplitter, callback: Callable=None):
        assert data_splitter.n_clients == self.n_clients, "Number of clients in data splitter and the FL environment must be the same"
        self.data_assignment = data_splitter.assignments
        self.clients = [Client(train_set=data_splitter.client_loader[i], 
                               optimizer_cfg=self.optimizer_cfg, 
                               loss_fn=self.loss_fn, 
                               local_epochs=self.n_epochs,
                               seed=self.seed) for i in range(self.n_clients)]

        self.server = Server(self.model, self.clients, self.elegibility_percentage, weighted=True, seed=self.seed)
        self.server.register_callback(callback)
        
    def run(self):
        self.server.init()
        self.server.fit(n_rounds=self.n_rounds)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(C={self.n_clients},R={self.n_rounds},E={self.n_epochs}," + \
               f"P={self.elegibility_percentage},seed={self.seed})"
