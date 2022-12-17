# fl-bench
Python module to benchmark federated learning algorithms

## TODO ASAP
- [ ] Check for seed consistency
- [ ] Check the correctness of SCAFFOLD
- [ ] Implement FedNova - https://arxiv.org/abs/2007.07481
- [ ] Implement FedDyn - https://openreview.net/pdf?id=B7v4QMR6Z9w
- [ ] Implement FedADMM - https://arxiv.org/pdf/2204.03529.pdf
- [ ] FedSGD: add support to `batch_size != 0`, i.e., the client can perform a local update on a subset (the only batch!) of the data
- [ ] Test logging on wandb
- [ ] Add support to validation
- [ ] Add client-side evaluations - useful to evaluate FedBN
- [ ] Add documentation + check typing

## DESIDERATA
- [ ] Add more algorithms
- [ ] Add more datasets
- [ ] Add support to tensorboard