from __future__ import annotations
import torch
import sys
sys.path.append(".")
sys.path.append("..")

from fl_bench.nets import (MNIST_2NN, MNIST_LR, MNIST_CNN, FEMNIST_CNN,  # NOQA
                           VGG9, FedavgCNN, LeNet5, MoonCNN, SimpleCNN,  # NOQA
                           ResNet9, ResNet18, ResNet34, ResNet50)  # NOQA


def test_mnist_2nn():

    model = MNIST_2NN()

    x = torch.randn(1, 28, 28)
    y = model(x)

    y1 = model.forward(x)
    z = model.forward_encoder(x)
    y2 = model.forward_head(z)

    assert z.shape == (1, 200)
    assert torch.allclose(y, y1)
    assert torch.allclose(y, y2)

    model = MNIST_2NN(softmax=True)

    y = model(x)
    assert y.shape == (1, 10)
    assert torch.allclose(y.sum(), torch.tensor(1.0))


def test_mnist_lr():
    model = MNIST_LR()
    x = torch.randn(1, 28, 28)
    y = model(x)

    assert y.shape == (1, 10)
    assert torch.allclose(y.sum(), torch.tensor(1.0))


def test_covnets():
    model = MNIST_CNN()
    x = torch.randn(1, 1, 28, 28)
    y1 = model(x)
    z = model.forward_encoder(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 10)
    assert torch.allclose(y1.sum(), torch.tensor(1.0))
    assert z.shape == (1, 1024)
    assert torch.allclose(y1, y2)

    model = FEMNIST_CNN()
    x = torch.randn(1, 1, 28, 28)
    y1 = model(x)
    z = model.forward_encoder(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 62)
    assert z.shape == (1, 3136)
    assert torch.allclose(y1, y2)

    model = VGG9()
    x = torch.randn(1, 1, 28, 28)
    y1 = model(x)
    z = model.forward_encoder(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 62)
    assert z.shape == (1, 512)
    assert torch.allclose(y1, y2)

    model = FedavgCNN()
    x = torch.randn(1, 3, 32, 32)
    y1 = model(x)
    z = model.forward_encoder(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 10)
    assert z.shape == (1, 4096)
    assert torch.allclose(y1, y2)

    model = LeNet5(10)
    x = torch.randn(1, 3, 32, 32)
    z = model.forward_encoder(x)
    y1 = model(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 10)
    assert z.shape == (1, 400)
    assert torch.allclose(y1, y2)

    model = MoonCNN()
    x = torch.randn(1, 3, 32, 32)
    z = model.forward_encoder(x)
    y1 = model(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 10)
    assert z.shape == (1, 400)
    assert torch.allclose(y1, y2)

    model = SimpleCNN()
    x = torch.randn(1, 3, 32, 32)
    z = model.forward_encoder(x)
    y1 = model(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 10)
    assert z.shape == (1, 400)
    assert torch.allclose(y1, y2)

    model = ResNet9()
    x = torch.randn(1, 3, 32, 32)
    z = model.forward_encoder(x)
    y1 = model(x)
    y2 = model.forward_head(z)
    assert y1.shape == (1, 100)
    assert z.shape == (1, 1024)
    assert torch.allclose(y1, y2)

    model = ResNet18()
    x = torch.randn(2, 3, 32, 32)
    y1 = model(x)
    assert y1.shape == (2, 10)

    model = ResNet34()
    x = torch.randn(2, 3, 32, 32)
    y1 = model(x)
    assert y1.shape == (2, 100)

    model = ResNet50()
    x = torch.randn(2, 3, 32, 32)
    y1 = model(x)
    assert y1.shape == (2, 100)


def test_recurrent():
    pass


if __name__ == "__main__":
    test_mnist_2nn()
    test_mnist_lr()
    test_covnets()
    test_recurrent()
