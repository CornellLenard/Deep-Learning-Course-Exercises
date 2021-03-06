import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import torchvision
import torchvision.transforms as transforms
import numpy as np


class AbstractNetwork(pl.LightningModule):

    def general_step(self, batch, batch_idx, mode):
        images, targets = batch

        # load X, y to device!
        images, targets = images.to(self.device), targets.to(self.device)

        # forward pass
        out = self.forward(images)

        # loss
        loss = F.cross_entropy(out, targets)

        predictions = out.argmax(axis=1)
        n_correct = (targets == predictions).sum()
        return loss, n_correct

    def general_end(self, outputs, mode):
        # average over all batches aggregated during one epoch
        avg_loss = torch.stack([x[mode + "_loss"] for x in outputs]).mean()
        total_correct = torch.stack([x[mode + "_n_correct"] for x in outputs]).sum().cpu().numpy()
        acc = total_correct / len(self.dataset[mode])
        return avg_loss, acc

    def training_step(self, batch, batch_idx):
        loss, n_correct = self.general_step(batch, batch_idx, "train")
        tensorboard_logs = {"train/loss": loss}
        return {
            "loss": loss,
            "train_n_correct": n_correct,
            "log": tensorboard_logs}

    def validation_step(self, batch, batch_idx):
        loss, n_correct = self.general_step(batch, batch_idx, "val")
        return {"val_loss": loss, "val_n_correct": n_correct}

    def test_step(self, batch, batch_idx):
        loss, n_correct = self.general_step(batch, batch_idx, "test")
        return {"test_loss": loss, "test_n_correct": n_correct}

    def validation_epoch_end(self, outputs):
        avg_loss, acc = self.general_end(outputs, "val")
        print("Val-Acc={}".format(acc))
        tensorboard_logs = {"val/loss": avg_loss, "val/acc": acc}
        return {"val_loss": avg_loss, "val_acc": acc, "log": tensorboard_logs}

    def prepare_data(self):

        # create dataset
        fashion_mnist_train = torchvision.datasets.FashionMNIST(
            root="../datasets", train=True, transform=transforms.ToTensor(), download=True)

        fashion_mnist_test = torchvision.datasets.FashionMNIST(
            root="../datasets", train=False, transform=transforms.ToTensor())

        torch.manual_seed(0)
        N = len(fashion_mnist_train)
        fashion_mnist_train, fashion_mnist_val = torch.utils.data.random_split(
            fashion_mnist_train, [int(N * 0.8), int(N * 0.2)])
        torch.manual_seed(torch.initial_seed())

        # assign to use in data loaders
        self.dataset = {}
        self.dataset["train"], self.dataset["val"], self.dataset["test"] = fashion_mnist_train, fashion_mnist_val, fashion_mnist_test

    def train_dataloader(self):
        return DataLoader(
            self.dataset["train"],
            shuffle=True,
            batch_size=self.batch_size)

    def val_dataloader(self):
        return DataLoader(self.dataset["val"], batch_size=self.batch_size)

    def test_dataloader(self):
        return DataLoader(self.dataset["test"], batch_size=self.batch_size)

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.model.parameters(), self.learning_rate)
        return optimizer

    def getTestAcc(self, loader=None):
        if not loader:
            loader = self.test_dataloader()

        scores = []
        labels = []

        for batch in loader:
            X, y = batch
            X, y = X.to(self.device), y.to(self.device)
            score = self.forward(X)
            scores.append(score.detach().cpu().numpy())
            labels.append(y.detach().cpu().numpy())

        scores = np.concatenate(scores, axis=0)
        labels = np.concatenate(labels, axis=0)

        predictions = scores.argmax(axis=1)
        acc = (labels == predictions).mean()
        return predictions, acc


class SimpleNetwork(AbstractNetwork):
    def __init__(
            self,
            batch_size,
            learning_rate,
            num_classes=10):
        super().__init__()

        # set hyper parameters
        self.batch_size = batch_size
        self.learning_rate = learning_rate

        self.model = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )
        self.fc = nn.Linear(32 * 7 * 7, num_classes)

    def forward(self, x):

        # x.shape = [batch_size, 1, 28, 28]
        # load to device!
        x = x.to(self.device)

        # feed x into model!
        x = self.model(x)
        x = x.view(x.shape[0], -1)
        x = self.fc(x)

        return x


class SpatialBatchNormNetwork(AbstractNetwork):

    def __init__(
            self,
            batch_size,
            learning_rate,
            num_classes=10):
        super().__init__()
        # set hyper parameters
        self.batch_size = batch_size
        self.learning_rate = learning_rate

        self.model = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
        )
        self.fc = nn.Linear(32 * 7 * 7, num_classes)

    def forward(self, x):
        # x.shape = [batch_size, 1, 28, 28]
        # load to device!
        x = x.to(self.device)

        # feed x into model!
        x = self.model(x)
        x = x.view(x.shape[0], -1)
        x = self.fc(x)

        return x
