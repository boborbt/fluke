from torch.nn import Module
import torch
from collections import OrderedDict
from typing import Iterable
from copy import deepcopy
import sys
sys.path.append(".")
sys.path.append("..")

from ..data import FastTensorDataLoader  # NOQA
from ..algorithms import CentralizedFL  # NOQA
from ..utils.model import diff_model  # NOQA
from ..server import Server  # NOQA
from ..client import Client  # NOQA


class FedAVGMServer(Server):
    def __init__(self,
                 model: Module,
                 test_data: FastTensorDataLoader,
                 clients: Iterable[Client],
                 eval_every: int = 1,
                 weighted: bool = True,
                 momentum: float = 0.9):
        super().__init__(model, test_data, clients, eval_every, weighted)
        self.hyper_params.update(momentum=momentum)
        self.optimizer = torch.optim.SGD(self.model.parameters(),
                                         lr=1.0,
                                         momentum=self.hyper_params.momentum,
                                         nesterov=True)

    def _aggregate(self, eligible: Iterable[Client]) -> None:
        avg_model_sd = OrderedDict()
        clients_sd = self._get_client_models(eligible)
        clients_diff = [diff_model(self.model.state_dict(), client_model)
                        for client_model in clients_sd]
        weights = self._get_client_weights(eligible)

        with torch.no_grad():
            for key in self.model.state_dict().keys():
                if "num_batches_tracked" in key:
                    avg_model_sd[key] = deepcopy(clients_sd[0][key])
                    continue
                for i, client_diff in enumerate(clients_diff):
                    if key not in avg_model_sd:
                        avg_model_sd[key] = weights[i] * client_diff[key]
                    else:
                        avg_model_sd[key] += weights[i] * client_diff[key]

        self.optimizer.zero_grad()
        for key, param in self.model.named_parameters():
            param.grad = avg_model_sd[key].data
        self.optimizer.step()


class FedAVGM(CentralizedFL):

    def get_server_class(self) -> Server:
        return FedAVGMServer
