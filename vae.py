import torch
import torch.nn as nn
import torch.nn.functional as F
from copy import deepcopy

class Encoder(nn.Module):
    def __init__(self, latent_dim):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 4, 2, 1), 
            nn.ReLU(),
            nn.Conv2d(32, 64, 4, 2, 1),
            nn.ReLU(),
            nn.Flatten()
        )
        self.fc_mu = nn.Linear(64 * 7 * 7, latent_dim)
        self.fc_logvar = nn.Linear(64 * 7 * 7, latent_dim)

    def forward(self, x):
        x = self.conv(x)
        mu = self.fc_mu(x)
        logvar = self.fc_logvar(x)
        return mu, logvar

def reparameterize(mu, logvar):
    std = torch.exp(0.5 * logvar)
    eps = torch.randn_like(std)
    return mu + eps * std

class Decoder(nn.Module):
    def __init__(self, latent_dim):
        super().__init__()
        self.fc = nn.Linear(latent_dim, 64 * 7 * 7)
        self.deconv = nn.Sequential(
            nn.ConvTranspose2d(64, 32, 4, 2, 1),  # -> (32, 14, 14)
            nn.ReLU(),
            nn.ConvTranspose2d(32, 1, 4, 2, 1),   # -> (1, 28, 28)
        )

    def forward(self, z):
        x = self.fc(z).view(-1, 64, 7, 7)
        return self.deconv(x)

class VAE(nn.Module):
    def __init__(self, latent_dim=20):
        super().__init__()
        self.encoder = Encoder(latent_dim)
        self.decoder = Decoder(latent_dim)

    def forward(self, x):
        mu, logvar = self.encoder(x)
        z = reparameterize(mu, logvar)
        x_recon = self.decoder(z)
        return x_recon, mu, logvar

def vae_loss(x, x_recon, mu, logvar):
    recon_loss = F.mse_loss(x_recon, x, reduction='sum')
    kl_div = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return recon_loss + kl_div

# Function to train the VAE
def train_vae(model, train_loader, val_loader, optimizer, device, epochs=20, patience=None):
    train_losses, val_losses = [], []
    best_loss = float('inf')
    counter = 0
    best_model = None

    for epoch in range(epochs):
        model.train()
        total_train_loss = 0
        for x, _ in train_loader:
            x = x.to(device)
            optimizer.zero_grad()
            x_recon, mu, logvar = model(x)
            loss = vae_loss(x, x_recon, mu, logvar)
            loss.backward()
            optimizer.step()
            total_train_loss += loss.item()

        model.eval()
        total_val_loss = 0
        with torch.no_grad():
            for x, _ in val_loader:
                x = x.to(device)
                x_recon, mu, logvar = model(x)
                total_val_loss += vae_loss(x, x_recon, mu, logvar).item()

        train_loss = total_train_loss / len(train_loader.dataset)
        val_loss = total_val_loss / len(val_loader.dataset)
        train_losses.append(train_loss)
        val_losses.append(val_loss)

        print(f"Epoch {epoch+1}, Training Loss (ELBO): {-train_loss:.2f}, Validation Loss (ELBO): {-val_loss:.2f}")

        if patience is not None:
            if val_loss < best_loss:
                best_loss = val_loss
                best_model = deepcopy(model.state_dict())
                counter = 0
            else:
                counter += 1
                if counter >= patience:
                    print("Early stopping.")
                    break

    if best_model is not None:
        model.load_state_dict(best_model)

    return model, train_losses, val_losses
