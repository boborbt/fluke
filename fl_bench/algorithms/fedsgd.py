from typing import Callable

from torch.nn import Module

from utils import OptimizerConfigurator

import sys; sys.path.append(".")
from fl_bench.algorithms import CentralizedFL


class FedSGD(CentralizedFL):
    def __init__(self,
                 n_clients: int,
                 n_rounds: int,
                 optimizer_cfg: OptimizerConfigurator,
                 model: Module,
                 loss_fn: Callable,
                 elegibility_percentage: float=0.5,
                 seed: int=42):
        
        super().__init__(n_clients,
                         n_rounds,
                         1,
                         model, 
                         optimizer_cfg, 
                         loss_fn,
                         elegibility_percentage,
                         seed)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(C={self.n_clients},R={self.n_rounds}," + \
               f"P={self.elegibility_percentage},seed={self.seed})"