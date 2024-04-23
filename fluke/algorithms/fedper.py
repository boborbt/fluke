from typing import Sequence
from copy import deepcopy
import torch
import sys
sys.path.append(".")
sys.path.append("..")

from ..algorithms import PersonalizedFL  # NOQA
from ..server import Server  # NOQA
from ..client import PFLClient  # NOQA
from ..comm import Message  # NOQA
from ..data import FastTensorDataLoader  # NOQA
from ..utils.model import safe_load_state_dict  # NOQA


# https://arxiv.org/abs/1912.00818
class FedPerClient(PFLClient):

    def _send_model(self):
        self.channel.send(Message(deepcopy(self.model.get_global()), "model", self), self.server)

    def _receive_model(self) -> None:
        if self.model is None:
            self.model = self.personalized_model
        msg = self.channel.receive(self, self.server, msg_type="model")
        safe_load_state_dict(self.model.get_global(), msg.payload.state_dict())


class FedPerServer(Server):

    def __init__(self,
                 model: torch.nn.Module,
                 test_data: FastTensorDataLoader,
                 clients: Sequence[PFLClient],
                 eval_every: int = 1,
                 weighted: bool = False):
        super().__init__(model, None, clients, eval_every, weighted)


class FedPer(PersonalizedFL):

    def get_client_class(self) -> PFLClient:
        return FedPerClient

    def get_server_class(self) -> Server:
        return FedPerServer