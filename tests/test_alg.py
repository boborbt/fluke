from torch.nn import CrossEntropyLoss
from torch.optim import SGD
import sys
sys.path.append(".")
sys.path.append("..")

from fluke import DDict, GlobalSettings  # NOQA
from fluke.data import DataSplitter  # NOQA
from fluke.data.datasets import Datasets  # NOQA
from fluke.client import Client, PFLClient  # NOQA
from fluke.server import Server  # NOQA
from fluke.nets import MNIST_2NN  # NOQA
from fluke.comm import ChannelObserver, Message  # NOQA
from fluke.algorithms import CentralizedFL, PersonalizedFL  # NOQA
from fluke.algorithms.fedavg import FedAVG  # NOQA
from fluke.utils import Configuration, Log, get_class_from_qualified_name, ServerObserver  # NOQA


def test_centralized_fl():
    hparams = DDict(
        # model="fluke.nets.MNIST_2NN",
        model=MNIST_2NN(),
        client=DDict(batch_size=32,
                     local_epochs=1,
                     loss=CrossEntropyLoss,
                     optimizer=DDict(
                         lr=0.1,
                         momentum=0.9),
                     scheduler=DDict(
                         step_size=1,
                         gamma=0.1)
                     ),
        server=DDict(weighted=True)
    )
    mnist = Datasets.MNIST("../data")
    splitter = DataSplitter(mnist)
    fl = CentralizedFL(2, splitter, hparams)

    assert fl.n_clients == 2
    assert fl.hyper_params == hparams
    assert len(fl.clients) == 2
    assert isinstance(fl.clients[0], Client)
    assert isinstance(fl.server, Server)
    assert isinstance(fl.server.model, MNIST_2NN)
    assert fl.clients[0].test_set is None
    assert isinstance(fl.clients[0].hyper_params.loss_fn, CrossEntropyLoss)

    hparams = DDict(
        model="fluke.nets.MNIST_2NN",
        client=DDict(batch_size=32,
                     local_epochs=1,
                     loss="CrossEntropyLoss",
                     optimizer=DDict(
                         lr=0.1,
                         momentum=0.9),
                     scheduler=DDict(
                         step_size=1,
                         gamma=0.1)
                     ),
        server=DDict(weighted=True)
    )
    mnist = Datasets.MNIST("../data")
    splitter = DataSplitter(mnist)
    fl = CentralizedFL(2, splitter, hparams)

    assert isinstance(fl.server.model, MNIST_2NN)
    assert isinstance(fl.clients[0].hyper_params.loss_fn, CrossEntropyLoss)

    assert fl.get_optimizer_class() == SGD
    assert fl.get_client_class() == Client
    assert fl.get_server_class() == Server

    class Observer(ServerObserver, ChannelObserver):
        def __init__(self):
            super().__init__()
            self.called_start = False
            self.called_end = False
            self.called_selected = False
            self.called_error = False
            self.called_finished = False

        def start_round(self, round, global_model):
            assert round == 1
            assert global_model is not None
            self.called_start = True

        def end_round(self,
                      round,
                      evals,
                      client_evals):
            assert round == 1
            assert len(client_evals) == 0
            assert "accuracy" in evals
            self.called_end = True

        def selected_clients(self, round, clients):
            assert len(clients) == 1
            assert round == 1
            self.called_selected = True

        def error(self, error):
            assert error == "error"
            self.called_error = True

        def finished(self,  client_evals):
            assert len(client_evals) == 0
            self.called_finished = True

        def message_received(self, message: Message):
            pass

    obs = Observer()
    fl.set_callbacks(obs)

    assert fl.server._observers == [obs]

    strfl = "CentralizedFL(model=fluke.nets.MNIST_2NN,Client[0-1](optim=OptCfg(SGD,lr=0.1," + \
        "momentum=0.9,StepLR(step_size=1,gamma=0.1)),batch_size=32,loss_fn=CrossEntropyLoss()," + \
        "local_epochs=1),Server(weighted=True))"

    assert str(fl).replace(" ", "").replace(
        "\n", "").replace("\t", "") == strfl
    assert fl.__repr__().replace(" ", "").replace(
        "\n", "").replace("\t", "") == strfl

    fl.run(1, 0.5)
    assert obs.called_start
    assert obs.called_end
    assert obs.called_selected
    assert obs.called_finished

    hparams = DDict(
        # model="fluke.nets.MNIST_2NN",
        model=MNIST_2NN(),
        client=DDict(batch_size=32,
                     local_epochs=1,
                     model=MNIST_2NN(),
                     loss=CrossEntropyLoss,
                     optimizer=DDict(
                         lr=0.1,
                         momentum=0.9),
                     scheduler=DDict(
                         step_size=1,
                         gamma=0.1)
                     ),
        server=DDict(weighted=True)
    )
    mnist = Datasets.MNIST("../data")
    splitter = DataSplitter(mnist)
    fl = PersonalizedFL(2, splitter, hparams)

    assert fl.n_clients == 2
    assert fl.hyper_params == hparams
    assert len(fl.clients) == 2
    assert isinstance(fl.clients[0], PFLClient)
    assert isinstance(fl.server, Server)
    assert isinstance(fl.server.model, MNIST_2NN)
    assert isinstance(fl.clients[0].personalized_model, MNIST_2NN)
    assert fl.clients[0].test_set is None
    assert isinstance(fl.clients[0].hyper_params.loss_fn, CrossEntropyLoss)


def _test_algo(exp_config, alg_config):
    cfg = Configuration(exp_config, alg_config)
    GlobalSettings().set_seed(cfg.exp.seed)
    GlobalSettings().set_device(cfg.exp.device)
    dataset = Datasets.get(**cfg.data.dataset)
    splitter = DataSplitter(dataset,
                            distribution=cfg.data.distribution.name,
                            dist_args=cfg.data.distribution.exclude("name"),
                            **cfg.data.exclude('dataset', 'distribution'))

    fl_algo_class = get_class_from_qualified_name(cfg.method.name)
    algo = fl_algo_class(cfg.protocol.n_clients,
                         splitter,
                         cfg.method.hyperparameters)

    log = Log()
    log.init(**cfg)
    algo.set_callbacks(log)
    # algo.run(cfg.protocol.n_rounds, cfg.protocol.eligible_perc)
    algo.run(1, 1)
    return algo, log


def test_fedavg():
    fedavg, log = _test_algo("./tests/configs/fedavg_exp.yaml", "./tests/configs/fedavg.yaml")
    # assert log.history[log.current_round]["accuracy"] >= 0.9642


def test_fedavgm():
    fedavgm, log = _test_algo("./tests/configs/fedavgm_exp.yaml", "./tests/configs/fedavgm.yaml")


def test_fedprox():
    fedprox, log = _test_algo("./tests/configs/fedprox_exp.yaml", "./tests/configs/fedprox.yaml")


def test_fedsgd():
    fedsgd, log = _test_algo("./tests/configs/fedsgd_exp.yaml", "./tests/configs/fedsgd.yaml")


def test_fedexp():
    fedexp, log = _test_algo("./tests/configs/fedexp_exp.yaml", "./tests/configs/fedexp.yaml")


def test_fedproto():
    fedproto, log = _test_algo("./tests/configs/fedproto_exp.yaml", "./tests/configs/fedproto.yaml")


def test_fedopt():
    fedopt, log = _test_algo("./tests/configs/fedopt_exp.yaml", "./tests/configs/fedopt.yaml")


if __name__ == "__main__":
    test_centralized_fl()
    test_fedavg()
    test_fedprox()
    test_fedsgd()
    test_fedexp()
    test_fedproto()
    test_fedopt()
    test_fedavgm()
