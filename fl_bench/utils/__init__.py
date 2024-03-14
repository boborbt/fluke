from __future__ import annotations
from copy import deepcopy

import json
import typer
import wandb
import importlib
import numpy as np
import pandas as pd
import psutil
from enum import Enum
from typing import Any, Iterable
from collections import OrderedDict

import torch
from torch.nn import Module, Parameter
from torch.optim import Optimizer
from torch.optim.lr_scheduler import StepLR

import rich
from rich.panel import Panel
from rich.pretty import Pretty

from fl_bench.data import DistributionEnum, FastTensorDataLoader
from fl_bench.evaluation import Evaluator
from fl_bench.data.datasets import DatasetsEnum

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from fl_bench import Message

class DeviceEnum(Enum):
    CPU: str = "cpu"
    CUDA: str = "cuda"
    AUTO: str = "auto"
    MPS: str = "mps"


class OptimizerConfigurator:
    """Optimizer configurator.

    Parameters
    ----------
    optimizer_class : type[Optimizer]
        The optimizer class.
    scheduler_kwargs : dict, optional
        The scheduler keyword arguments, by default None. If None, the scheduler
        is set to StepLR with step_size=1 and gamma=1.
    **optimizer_kwargs
        The optimizer keyword arguments.
    """ 
    def __init__(self,
                 optimizer_class: type[Optimizer], 
                 scheduler_kwargs: dict=None,
                 **optimizer_kwargs):
        self.optimizer = optimizer_class
        if scheduler_kwargs is not None:
            self.scheduler_kwargs = scheduler_kwargs
        else:
            self.scheduler_kwargs = {"step_size": 1, "gamma": 1}
        self.optimizer_kwargs = optimizer_kwargs
    
    def __call__(self, model: Module, **override_kwargs):
        if override_kwargs:
            self.optimizer_kwargs.update(override_kwargs)
        optimizer = self.optimizer(model.parameters(), **self.optimizer_kwargs)
        scheduler = StepLR(optimizer, **self.scheduler_kwargs)
        return optimizer, scheduler
    
    def __str__(self) -> str:
        to_str = f"OptCfg({self.optimizer.__name__},"
        to_str += ",".join([f"{k}={v}" for k, v in self.optimizer_kwargs.items()])
        to_str += "," + ",".join([f"{k}={v}" for k, v in self.scheduler_kwargs.items()])
        to_str += ")"
        return to_str


class LogEnum(Enum):
    LOCAL = "local"
    WANDB = "wandb"

    def logger(self, classification_eval, eval_every, **wandb_config):
        if self == LogEnum.LOCAL:
            return Log(classification_eval, 
                       eval_every if eval_every else 1)
        else:
            return WandBLog(
                classification_eval,
                eval_every if eval_every else 1,
                **wandb_config)

class ServerObserver():
    
    def start_round(self, round: int, global_model: Any):
        pass

    def end_round(self, round: int, global_model: Any, data: FastTensorDataLoader, client_evals: Iterable[Any]):
        pass

    def selected_clients(self, round: int, clients: Iterable):
        pass

    def error(self, error: str):
        pass

    def finished(self,  client_evals: Iterable[Any]):
        pass


class ChannelObserver():
    
    def message_received(self, message: Message):
        pass


class Log(ServerObserver, ChannelObserver):

    def __init__(self, evaluator: Evaluator, eval_every: int=1):
        self.evaluator = evaluator
        self.history = {}
        self.client_history = {}
        self.comm_costs = {0: 0}
        self.current_round = 0
        self.eval_every = eval_every
    
    def init(self, **kwargs):
        rich.print(Panel(Pretty(kwargs, expand_all=True), title=f"Configuration"))
    
    def start_round(self, round: int, global_model: Module):
        self.comm_costs[round] = 0
        self.current_round = round

        if round == 1 and self.comm_costs[0] > 0:
            rich.print(Panel(Pretty({"comm_costs": self.comm_costs[0]}), title=f"Round: {round-1}"))

    def end_round(self, round: int, global_model: Module, data: FastTensorDataLoader, client_evals: Iterable[Any]):
        if round % self.eval_every == 0:
            self.history[round] = self.evaluator(global_model, data)
            stats = { 'global': self.history[round] }

            if client_evals:
                client_mean = pd.DataFrame(client_evals).mean(numeric_only=True).to_dict()
                client_mean = {k: np.round(float(v), 5) for k, v in client_mean.items()}
                self.client_history[round] = client_mean
                stats['local'] = client_mean
            
            stats['comm_cost'] = self.comm_costs[round]

            rich.print(Panel(Pretty(stats, expand_all=True), title=f"Round: {round}"))
        rich.print(f"  MEMORY USAGE: {psutil.virtual_memory().used / 1e9:.2f} GB")
    
    def message_received(self, message: Message):
        self.comm_costs[self.current_round] += message.get_size()
    
    def finished(self, client_evals: Iterable[Any]):
        if client_evals:
            client_mean = pd.DataFrame(client_evals).mean(numeric_only=True).to_dict()
            client_mean = {k: np.round(float(v), 5) for k, v in client_mean.items()}
            self.client_history[self.current_round + 1] = client_mean
            rich.print(Panel(Pretty(client_mean, expand_all=True), title=f"Overall local performance"))
        
        if self.history[self.current_round]:
            rich.print(Panel(Pretty(self.history[self.current_round], expand_all=True), title=f"Overall global performance"))
        
        rich.print(Panel(Pretty({"comm_costs": sum(self.comm_costs.values())}, expand_all=True), 
                         title=f"Total communication cost"))
    
    def save(self, path: str):
        json_to_save = {
            "perf_global": self.history,
            "comm_costs": self.comm_costs,
            "perf_local": self.client_history
        }
        with open(path, 'w') as f:
            json.dump(json_to_save, f, indent=4)
        
    def error(self, error: str):
        rich.print(f"[bold red]Error: {error}[/bold red]")


class WandBLog(Log):
    def __init__(self, evaluator: Evaluator, eval_every: int, **config):
        super().__init__(evaluator, eval_every)
        self.config = config
        
    def init(self, **kwargs):
        super().init(**kwargs)
        self.config["config"] = kwargs
        self.run = wandb.init(**self.config)
    
    def start_round(self, round: int, global_model: Module):
        super().start_round(round, global_model)
        if round == 1 and self.comm_costs[0] > 0:
            self.run.log({"comm_costs": self.comm_costs[0]})

    def end_round(self, round: int, global_model: Module, data: FastTensorDataLoader, client_evals: Iterable[Any]):
        super().end_round(round, global_model, data, client_evals)
        if round % self.eval_every == 0:
            self.run.log({ "global": self.history[round]}, step=round)
            self.run.log({ "comm_cost": self.comm_costs[round]}, step=round)
            if client_evals:
                self.run.log({ "local": self.client_history[round]}, step=round)
    
    def finished(self, client_evals: Iterable[Any]):
        super().finished(client_evals)
        if client_evals:
            self.run.log({"local" : self.client_history[self.current_round+1]}, step=self.current_round+1)
    
    def save(self, path: str):
        super().save(path)
        self.run.finish()


def _get_class_from_str(module_name: str, class_name: str) -> Any:
    module = importlib.import_module(module_name)
    class_ = getattr(module, class_name)
    return class_

def get_loss(lname: str) -> torch.nn.Module:
    return _get_class_from_str("torch.nn", lname)()

def get_model(mname:str, **kwargs) -> torch.nn.Module:
    return _get_class_from_str("net", mname)(**kwargs)

def get_scheduler(sname:str) -> torch.nn.Module:
    return _get_class_from_str("torch.optim.lr_scheduler", sname)

def cli_option(default: Any, help: str) -> Any:
    return typer.Option(default=None, show_default=default, help=help)

def clear_cache(ipc: bool=False):
    torch.cuda.empty_cache()
    if ipc:
        torch.cuda.ipc_collect()


class DDict(dict):
    """A dictionary that can be accessed with dot notation recursively."""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__

    def __init__(self, d: dict):
        self.update(d)
    
    def update(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                self[k] = DDict(v)
            else:
                self[k] = v
    
    def exclude(self, *keys: str):
        return DDict({k: v for k, v in self.items() if k not in keys})

                
class Configuration(DDict):
    def __init__(self, config_exp_path: str, config_alg_path: str):
        with open(config_exp_path) as f:
            config_exp = json.load(f)
        with open(config_alg_path) as f:
            config_alg = json.load(f)

        self.update(config_exp)
        self.update({"method": config_alg})
        self._fix_enums()
    
    def _fix_enums(self):
        self.data.distribution = DistributionEnum(self.data.distribution)
        self.data.dataset.name = DatasetsEnum(self.data.dataset.name)
        self.exp.device = DeviceEnum(self.exp.device) if self.exp.device else DeviceEnum.CPU
        self.log.logger = LogEnum(self.log.logger)
    
    # def __str__(self) -> str:
    #     return f"{self.method.name}_data({self.data.dataset.value},{self.data.distribution.value}{',std' if self.data.standardize else ''})" + \
    #            f"_proto(C{self.protocol.n_clients},R{self.protocol.n_rounds},E{self.protocol.eligible_perc})" + \
    #            f"_seed({self.exp.seed})"

    # def __repr__(self) -> str:
    #     return self.__str__()

def import_module_from_str(name: str) -> Any:
    components = name.split('.')
    mod = importlib.import_module(".".join(components[:-1]))
    mod = getattr(mod, components[-1])
    return mod
