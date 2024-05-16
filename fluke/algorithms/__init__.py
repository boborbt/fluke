"""This module contains the implementation of several the federated learning algorithms."""
from __future__ import annotations
import torch
from typing import Callable, Union, Any, Iterable
from copy import deepcopy
import sys
sys.path.append(".")
sys.path.append("..")

from .. import DDict  # NOQA
from ..utils import OptimizerConfigurator, get_loss, get_model  # NOQA
from ..data import DataSplitter, FastDataLoader  # NOQA
from ..server import Server  # NOQA
from ..client import Client, PFLClient  # NOQA

__all__ = [
    'CentralizedFL',
    'PersonalizedFL',
    'apfl',
    'ccvr',
    'ditto',
    'fedamp',
    'fedavg',
    'fedavgm',
    'fedbabu',
    'fedbn',
    'feddyn',
    'fedexp',
    'fedhyperproto',
    'fedlc',
    'fednh',
    'fednova',
    'fedopt',
    'fedper',
    'fedproto',
    'fedprox',
    'fedrep',
    'fedsgd',
    'lg_fedavg',
    'moon',
    'per_fedavg',
    'pfedme',
    'scaffold',
    'superfed'
]


class CentralizedFL():
    """Centralized Federated Learning algorithm.
    This class is a generic implementation of a centralized federated learning algorithm that
    follows the Federated Averaging workflow. This class represents the entry point to the
    federated learning algorithm.
    Each new algorithm should inherit from this class and implement the specific logic of the
    algorithm. The main components of the algorithm are:

    - ``Clients``: Each client should implement :class:`fluke.client.Client` class and the specific
      specialization must be defined in the :meth:`get_client_class` method. The initialization of
      the clients is done in the :meth:`init_clients` method.
    - ``Server``: The server is the entity that coordinates the training process. It should
      implement the :class:`fluke.server.Server` class and the specific specialization must be
      defined in the :meth:`get_server_class` method. The initialization of the server is done in
      the :meth:`init_server` method.
    - ``Optimizer``: The optimizer used by the clients. The default optimizer class is defined in
      the :meth:`get_optimizer_class` method.

    To run the algorithm, the :meth:`run` method should be called with the number of rounds and the
    percentage of eligible clients. This method will call the :meth:`Server.fit` method which will
    orchestrate the training process.

    Args:
        n_clients (int): Number of clients.
        data_splitter (DataSplitter): Data splitter object.
        hyper_params (DDict): Hyperparameters of the algorithm. This set of hyperparameteers should
          be divided in two parts: the client hyperparameters and the server hyperparameters.

    See Also:
        - :class:`fluke.client.Client`
        - :class:`fluke.server.Server`
        - :class:`PersonalizedFL`
    """

    def __init__(self,
                 n_clients: int,
                 data_splitter: DataSplitter,
                 hyper_params: DDict):
        self.hyper_params = hyper_params
        self.n_clients = n_clients
        (clients_tr_data, clients_te_data), server_data = \
            data_splitter.assign(n_clients, hyper_params.client.batch_size)
        # Federated model
        model = get_model(mname=hyper_params.model
                          # **hyper_params.net_args if 'net_args' in hyper_params else {}
                          ) if isinstance(hyper_params.model, str) else hyper_params.model

        self.init_clients(clients_tr_data, clients_te_data, hyper_params.client)
        self.init_server(model, server_data, hyper_params.server)

    def get_optimizer_class(self) -> torch.optim.Optimizer:
        """Get the optimizer class.

        Returns:
            torch.optim.Optimizer: Optimizer class.
        """
        return torch.optim.SGD

    def get_client_class(self) -> Client:
        """Get the client class.
        This method should be overriden by the subclasses when a different client class is defined.
        This allows to reuse all the logic of the algorithm and only change the client class.

        Returns:
            Client: Client class.
        """
        return Client

    def get_server_class(self) -> Server:
        """Get the server class.
        This method should be overriden by the subclasses when a different server class is defined.
        This allows to reuse all the logic of the algorithm and only change the server class.

        Returns:
            Server: Server class.
        """
        return Server

    def init_clients(self,
                     clients_tr_data: list[FastDataLoader],
                     clients_te_data: list[FastDataLoader],
                     config: DDict) -> None:
        """Initialize the clients.

        Args:
            clients_tr_data (list[FastDataLoader]): List of training data loaders, one for
               each client.
            clients_te_data (list[FastDataLoader]): List of test data loaders, one for
               each client. The test data loaders can be ``None``.
            config (DDict): Configuration of the clients.

        Important:
            For more deatils about the configuration of the clients, see the
            :ref:`configuration <configuration>` page.

        See Also:
            :class:`fluke.client.Client`
        """

        if "name" not in config.optimizer:
            config.optimizer.name = self.get_optimizer_class()
        optimizer_cfg = OptimizerConfigurator(optimizer_cfg=config.optimizer,
                                              scheduler_cfg=config.scheduler)
        self.loss = get_loss(config.loss) if isinstance(config.loss, str) else config.loss
        self.clients = [
            self.get_client_class()(
                index=i,
                train_set=clients_tr_data[i],
                test_set=clients_te_data[i],
                optimizer_cfg=optimizer_cfg,
                loss_fn=self.loss,
                **config.exclude('optimizer', 'loss', 'batch_size', 'scheduler')
            )
            for i in range(self.n_clients)]

    def init_server(self, model: Any, data: FastDataLoader, config: DDict):
        """Initailize the server.

        Args:
            model (Any): The global model.
            data (FastDataLoader): The server-side test set.
            config (DDict): Configuration of the server.
        """
        self.server = self.get_server_class()(model, data, self.clients, **config)

    def set_callbacks(self, callbacks: Union[Callable, Iterable[Callable]]):
        """Set the callbacks.

        Args:
            callbacks (Union[Callable, Iterable[Callable]]): Callbacks to attach to the algorithm.
        """
        self.server.attach(callbacks)
        self.server.channel.attach(callbacks)

    def run(self, n_rounds: int, eligible_perc: float):
        self.server.fit(n_rounds=n_rounds, eligible_perc=eligible_perc)

    def __str__(self) -> str:
        algo_hp = ",\n\t".join(
            [f"{h}={str(v)}"
             for h, v in self.hyper_params.items() if h not in ['client', 'server']]
        )
        algo_hp = f"\n\t{algo_hp}," if algo_hp else ""
        client_str = str(self.clients[0]).replace("[0]", f"[0-{self.n_clients-1}]")
        return f"{self.__class__.__name__}({algo_hp}\n\t{client_str},\n\t{self.server}\n)"

    def __repr__(self) -> str:
        return self.__str__()


class PersonalizedFL(CentralizedFL):
    """Personalized Federated Learning algorithm. This class is a simple extension of the
    :class:`CentralizedFL` class where the clients are expected to implement the
    :class:`fluke.client.PFLClient` class (see :meth:`get_client_class`). The main difference with
    respect to the :class:`CentralizedFL` class is that the clients initialization requires a model
    that is the personalized model of the client.

    Important:
        Differently from :class:`CentralizedFL`, which is actually the FedAvg algorithm, the
        :class:`PersonalizedFL` class must not be used as is because it is a generic implementation
        of a personalized federated learning algorithm. The subclasses of this class should
        implement the specific logic of the personalized federated learning algorithm.

    See Also:
        - :class:`CentralizedFL`
        - :class:`fluke.client.PFLClient`
    """

    def get_client_class(self) -> PFLClient:
        return PFLClient

    def init_clients(self,
                     clients_tr_data: list[FastDataLoader],
                     clients_te_data: list[FastDataLoader],
                     config: DDict) -> None:

        model = get_model(mname=config.model) if isinstance(config.model, str) else config.model
        if "name" not in config.optimizer:
            config.optimizer.name = self.get_optimizer_class()
        optimizer_cfg = OptimizerConfigurator(optimizer_cfg=config.optimizer,
                                              scheduler_cfg=config.scheduler)
        self.loss = get_loss(config.loss) if isinstance(config.loss, str) else config.loss
        self.clients = [
            self.get_client_class()(
                index=i,
                model=deepcopy(model),
                train_set=clients_tr_data[i],
                test_set=clients_te_data[i],
                optimizer_cfg=optimizer_cfg,
                loss_fn=self.loss,
                **config.exclude('optimizer', 'loss', 'batch_size', 'model', 'scheduler')
            )
            for i in range(self.n_clients)]
