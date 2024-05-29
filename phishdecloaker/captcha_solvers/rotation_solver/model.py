import torch
import torch.nn as nn
from torchvision import models


class RotModel(nn.Module):
    def __init__(self) -> None:
        """
        Rotation estimation network w/ RegNet as backbone.
        Outputs [0, 1], which maps to [0, 360] degrees of rotation.
        Attributes:
            train: enable model training.
        """
        super().__init__()

        self.backbone = models.efficientnet_b3(weights=models.EfficientNet_B3_Weights)

        self.fc_channels = self.backbone.classifier[-1].in_features
        self.fc0 = nn.Linear(self.fc_channels, self.fc_channels)
        self.act = nn.LeakyReLU()
        self.fc1 = nn.Linear(self.fc_channels, 1)
        del self.backbone.classifier

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: tensor of shape [batch_size, 224, 224]
        Returns:
            tensor of shape [batch_size, 1]
        """
        x = self.backbone.features(x)
        x = self.backbone.avgpool(x)
        x = x.flatten(start_dim=1)

        x = self.fc0(x)
        x = self.act(x)
        x = self.fc1(x)

        x.squeeze_(dim=1)
        return x
