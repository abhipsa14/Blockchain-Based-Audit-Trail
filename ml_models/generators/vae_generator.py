"""
VAE Generator Module
Variational Autoencoder for synthetic tabular data generation with audit logging.
"""

import hashlib
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import os
import sys
import pickle
import warnings
warnings.filterwarnings('ignore')

# Deep learning imports
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not installed. VAE generator will not be available.")

from sklearn.preprocessing import StandardScaler, LabelEncoder


@dataclass
class VAEAuditLog:
    """Audit log entry for VAE generation."""
    generation_id: str
    timestamp: str
    generator_type: str
    input_data_hash: str
    output_data_hash: str
    num_rows_input: int
    num_rows_output: int
    columns: List[str]
    latent_dim: int
    epochs: int
    reconstruction_loss: float
    kl_loss: float
    generation_time_seconds: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class VAEEncoder(nn.Module):
    """Encoder network for VAE."""
    
    def __init__(self, input_dim: int, hidden_dim: int, latent_dim: int):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc_mu = nn.Linear(hidden_dim // 2, latent_dim)
        self.fc_logvar = nn.Linear(hidden_dim // 2, latent_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        h = self.dropout(self.relu(self.fc1(x)))
        h = self.dropout(self.relu(self.fc2(h)))
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        return mu, logvar


class VAEDecoder(nn.Module):
    """Decoder network for VAE."""
    
    def __init__(self, latent_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.fc1 = nn.Linear(latent_dim, hidden_dim // 2)
        self.fc2 = nn.Linear(hidden_dim // 2, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, output_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, z):
        h = self.dropout(self.relu(self.fc1(z)))
        h = self.dropout(self.relu(self.fc2(h)))
        return self.fc3(h)


class TabularVAE(nn.Module):
    """Complete VAE for tabular data."""
    
    def __init__(self, input_dim: int, hidden_dim: int = 256, latent_dim: int = 32):
        super().__init__()
        self.encoder = VAEEncoder(input_dim, hidden_dim, latent_dim)
        self.decoder = VAEDecoder(latent_dim, hidden_dim, input_dim)
        self.latent_dim = latent_dim
        
    def reparameterize(self, mu, logvar):
        """Reparameterization trick."""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std
    
    def forward(self, x):
        mu, logvar = self.encoder(x)
        z = self.reparameterize(mu, logvar)
        reconstruction = self.decoder(z)
        return reconstruction, mu, logvar
    
    def generate(self, n_samples: int, device: str = 'cpu'):
        """Generate new samples from the latent space."""
        with torch.no_grad():
            z = torch.randn(n_samples, self.latent_dim).to(device)
            samples = self.decoder(z)
        return samples


class AuditableVAE:
    """
    VAE wrapper with comprehensive audit logging.
    
    Features:
    - Automatic hash generation for input/output data
    - Training parameter logging
    - Generation metadata tracking
    - Audit trail export
    """
    
    def __init__(self, 
                 latent_dim: int = 32,
                 hidden_dim: int = 256,
                 epochs: int = 100,
                 batch_size: int = 256,
                 learning_rate: float = 1e-3,
                 verbose: bool = True):
        """
        Initialize Auditable VAE.
        
        Args:
            latent_dim: Dimension of latent space
            hidden_dim: Hidden layer dimension
            epochs: Number of training epochs
            batch_size: Batch size for training
            learning_rate: Learning rate
            verbose: Whether to print progress
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for VAE generator")
            
        self.latent_dim = latent_dim
        self.hidden_dim = hidden_dim
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.verbose = verbose
        
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.columns = []
        self.categorical_columns = []
        self.numerical_columns = []
        
        # Audit state
        self.audit_logs: List[VAEAuditLog] = []
        self.is_fitted = False
        self.training_data_hash = None
        self.training_start_time = None
        self.training_end_time = None
        self.final_recon_loss = None
        self.final_kl_loss = None
        
        # Device
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
    def _compute_hash(self, data: pd.DataFrame) -> str:
        """Compute deterministic hash of DataFrame."""
        data_str = data.to_csv(index=False)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def _preprocess(self, data: pd.DataFrame) -> np.ndarray:
        """Preprocess data for VAE."""
        processed = data.copy()
        
        # Encode categorical columns
        for col in self.categorical_columns:
            if col in processed.columns:
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    processed[col] = self.label_encoders[col].fit_transform(
                        processed[col].astype(str)
                    )
                else:
                    # Handle unseen categories
                    processed[col] = processed[col].astype(str)
                    known = set(self.label_encoders[col].classes_)
                    processed[col] = processed[col].apply(
                        lambda x: x if x in known else self.label_encoders[col].classes_[0]
                    )
                    processed[col] = self.label_encoders[col].transform(processed[col])
        
        return processed.values.astype(np.float32)
    
    def _postprocess(self, data: np.ndarray) -> pd.DataFrame:
        """Convert generated data back to DataFrame."""
        df = pd.DataFrame(data, columns=self.columns)
        
        # Decode categorical columns
        for col in self.categorical_columns:
            if col in df.columns:
                # Round to nearest integer and clip to valid range
                n_classes = len(self.label_encoders[col].classes_)
                df[col] = np.clip(np.round(df[col]).astype(int), 0, n_classes - 1)
                df[col] = self.label_encoders[col].inverse_transform(df[col])
        
        # Round numerical columns appropriately
        for col in self.numerical_columns:
            if col in df.columns:
                # Check if original was integer
                df[col] = df[col].astype(float)
        
        return df
    
    def fit(self, 
            data: pd.DataFrame,
            categorical_columns: Optional[List[str]] = None) -> 'AuditableVAE':
        """
        Fit the VAE on training data.
        
        Args:
            data: Training data
            categorical_columns: List of categorical column names
        """
        self.training_start_time = datetime.now().isoformat()
        
        # Store metadata
        self.columns = list(data.columns)
        self.categorical_columns = categorical_columns or []
        self.numerical_columns = [c for c in self.columns if c not in self.categorical_columns]
        self.training_data_hash = self._compute_hash(data)
        
        if self.verbose:
            print(f"Training VAE on {len(data)} rows, {len(self.columns)} columns")
            print(f"Input data hash: {self.training_data_hash}...")
        
        # Preprocess
        X = self._preprocess(data)
        X_scaled = self.scaler.fit_transform(X)
        
        # Create model
        input_dim = X_scaled.shape[1]
        self.model = TabularVAE(input_dim, self.hidden_dim, self.latent_dim).to(self.device)
        
        # Create data loader
        dataset = TensorDataset(torch.FloatTensor(X_scaled))
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Optimizer
        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Training loop
        self.model.train()
        for epoch in range(self.epochs):
            total_recon_loss = 0
            total_kl_loss = 0
            n_batches = 0
            
            for batch in loader:
                x = batch[0].to(self.device)
                
                optimizer.zero_grad()
                
                recon, mu, logvar = self.model(x)
                
                # Reconstruction loss
                recon_loss = nn.MSELoss()(recon, x)
                
                # KL divergence
                kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp()) / x.size(0)
                
                # Total loss
                loss = recon_loss + 0.01 * kl_loss
                
                loss.backward()
                optimizer.step()
                
                total_recon_loss += recon_loss.item()
                total_kl_loss += kl_loss.item()
                n_batches += 1
            
            avg_recon = total_recon_loss / n_batches
            avg_kl = total_kl_loss / n_batches
            
            if self.verbose and (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{self.epochs} - Recon: {avg_recon:.4f}, KL: {avg_kl:.4f}")
        
        self.final_recon_loss = avg_recon
        self.final_kl_loss = avg_kl
        self.training_end_time = datetime.now().isoformat()
        self.is_fitted = True
        
        if self.verbose:
            print(f"Training completed!")
        
        return self
    
    def sample(self, n_samples: int) -> pd.DataFrame:
        """
        Generate synthetic samples.
        
        Args:
            n_samples: Number of samples to generate
            
        Returns:
            DataFrame with synthetic data
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before sampling")
        
        start_time = datetime.now()
        
        if self.verbose:
            print(f"Generating {n_samples} synthetic samples...")
        
        self.model.eval()
        generated = self.model.generate(n_samples, self.device)
        generated_np = generated.cpu().numpy()
        
        # Inverse transform
        generated_unscaled = self.scaler.inverse_transform(generated_np)
        
        # Convert to DataFrame
        synthetic_data = self._postprocess(generated_unscaled)
        
        end_time = datetime.now()
        generation_time = (end_time - start_time).total_seconds()
        
        # Create audit log
        generation_id = hashlib.sha256(
            f"{self.training_data_hash}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        output_hash = self._compute_hash(synthetic_data)
        
        audit_log = VAEAuditLog(
            generation_id=generation_id,
            timestamp=datetime.now().isoformat(),
            generator_type="AuditableVAE",
            input_data_hash=self.training_data_hash,
            output_data_hash=output_hash,
            num_rows_input=0,  # Not stored
            num_rows_output=n_samples,
            columns=self.columns,
            latent_dim=self.latent_dim,
            epochs=self.epochs,
            reconstruction_loss=self.final_recon_loss,
            kl_loss=self.final_kl_loss,
            generation_time_seconds=generation_time
        )
        
        self.audit_logs.append(audit_log)
        
        if self.verbose:
            print(f"Generation ID: {generation_id}")
            print(f"Output data hash: {output_hash}...")
            print(f"Generation completed in {generation_time:.2f} seconds")
        
        return synthetic_data
    
    def get_latest_audit_log(self) -> Optional[VAEAuditLog]:
        """Get the most recent audit log."""
        return self.audit_logs[-1] if self.audit_logs else None
    
    def export_audit_trail(self, filepath: str) -> None:
        """Export complete audit trail to JSON."""
        audit_trail = {
            'generator_type': 'AuditableVAE',
            'training_data_hash': self.training_data_hash,
            'model_config': {
                'latent_dim': self.latent_dim,
                'hidden_dim': self.hidden_dim,
                'epochs': self.epochs,
                'batch_size': self.batch_size
            },
            'training_start': self.training_start_time,
            'training_end': self.training_end_time,
            'generation_logs': [log.to_dict() for log in self.audit_logs]
        }
        
        with open(filepath, 'w') as f:
            json.dump(audit_trail, f, indent=2)
        
        if self.verbose:
            print(f"Audit trail exported to: {filepath}")
    
    def save(self, filepath: str) -> None:
        """Save the trained model to a file."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before saving")
        
        # Save PyTorch model separately
        model_path = filepath.replace('.pkl', '_vae_model.pt')
        torch.save(self.model.state_dict(), model_path)
        
        # Save metadata
        metadata = {
            'latent_dim': self.latent_dim,
            'hidden_dim': self.hidden_dim,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'is_fitted': self.is_fitted,
            'training_data_hash': self.training_data_hash,
            'columns': self.columns,
            'categorical_columns': self.categorical_columns,
            'numerical_columns': self.numerical_columns,
            'training_start_time': self.training_start_time,
            'training_end_time': self.training_end_time,
            'final_recon_loss': self.final_recon_loss,
            'final_kl_loss': self.final_kl_loss,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders,
            'audit_logs': [log.to_dict() for log in self.audit_logs],
            'model_path': model_path
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(metadata, f)
        
        if self.verbose:
            print(f"Model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str, verbose: bool = True) -> 'AuditableVAE':
        """Load a trained model from a file."""
        with open(filepath, 'rb') as f:
            metadata = pickle.load(f)
        
        instance = cls(
            latent_dim=metadata['latent_dim'],
            hidden_dim=metadata['hidden_dim'],
            epochs=metadata['epochs'],
            batch_size=metadata['batch_size'],
            learning_rate=metadata['learning_rate'],
            verbose=verbose
        )
        
        instance.is_fitted = metadata['is_fitted']
        instance.training_data_hash = metadata['training_data_hash']
        instance.columns = metadata['columns']
        instance.categorical_columns = metadata['categorical_columns']
        instance.numerical_columns = metadata['numerical_columns']
        instance.training_start_time = metadata['training_start_time']
        instance.training_end_time = metadata['training_end_time']
        instance.final_recon_loss = metadata['final_recon_loss']
        instance.final_kl_loss = metadata['final_kl_loss']
        instance.scaler = metadata['scaler']
        instance.label_encoders = metadata['label_encoders']
        
        # Load PyTorch model
        model_path = metadata.get('model_path', filepath.replace('.pkl', '_vae_model.pt'))
        if os.path.exists(model_path):
            input_dim = len(instance.columns)
            instance.model = TabularVAE(input_dim, instance.hidden_dim, instance.latent_dim)
            instance.model.load_state_dict(torch.load(model_path, map_location=instance.device))
            instance.model.to(instance.device)
        
        if verbose:
            print(f"Model loaded from {filepath}")
        
        return instance


def generate_auditable_vae_data(
    real_data: pd.DataFrame,
    categorical_columns: Optional[List[str]] = None,
    n_samples: Optional[int] = None,
    latent_dim: int = 32,
    epochs: int = 100,
    verbose: bool = True
) -> Tuple[pd.DataFrame, VAEAuditLog]:
    """
    Generate synthetic data with VAE and full audit trail.
    
    Args:
        real_data: Original training data
        categorical_columns: List of categorical columns
        n_samples: Number of samples (default: same as input)
        latent_dim: Latent space dimension
        epochs: Training epochs
        verbose: Print progress
        
    Returns:
        Tuple of (synthetic_data, audit_log)
    """
    n_samples = n_samples or len(real_data)
    
    generator = AuditableVAE(latent_dim=latent_dim, epochs=epochs, verbose=verbose)
    generator.fit(real_data, categorical_columns)
    synthetic_data = generator.sample(n_samples)
    
    return synthetic_data, generator.get_latest_audit_log()


if __name__ == "__main__":
    # Test with sample data
    print("Testing AuditableVAE...")
    
    # Create sample data
    np.random.seed(42)
    n = 1000
    data = pd.DataFrame({
        'age': np.random.randint(18, 80, n),
        'income': np.random.normal(50000, 15000, n),
        'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n),
        'employed': np.random.choice(['Yes', 'No'], n)
    })
    
    # Generate synthetic data
    synthetic, audit_log = generate_auditable_vae_data(
        data,
        categorical_columns=['education', 'employed'],
        n_samples=500,
        epochs=50,
        verbose=True
    )
    
    print("\nSynthetic Data Sample:")
    print(synthetic.head())
    print(f"\nAudit Log: {audit_log.generation_id}")
