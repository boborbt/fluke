import sys; sys.path.append(".")
from typing import Iterable

from fl_bench.data import FastTensorDataLoader
from fl_bench.server import Server
from copy import deepcopy
from torch.nn import Module

from fl_bench import Message
from fl_bench.client import Client, PFLClient
from fl_bench.algorithms import PersonalizedFL

# FEDerated DISEntanglment Learning
class FedDiselClient(PFLClient):

    def _send_model(self):
        self.channel.send(Message(deepcopy(self.model.fed_E), "model", self), self.server)

    def _receive_model(self) -> None:
        if self.model is None:
            self.model = self.personalized_model
        msg = self.channel.receive(self, self.server, msg_type="model")
        self.model.fed_E.load_state_dict(msg.payload.state_dict())

class FedDiselServer(Server):

    def __init__(self,
                 model: Module,
                 test_data: FastTensorDataLoader,
                 clients: Iterable[Client], 
                 weighted: bool=False):
        super().__init__(model, None, clients, weighted)

class FedDisel(PersonalizedFL):
    
    def get_client_class(self) -> Client:
        return FedDiselClient

    def get_server_class(self) -> Server:
        return FedDiselServer
