"""
Auditable CTGAN Module
CTGAN wrapper with built-in audit logging and hash generation.
"""

import hashlib
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import os
import sys
import pickle

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from ctgan import CTGAN
    CTGAN_AVAILABLE = True
except ImportError:
    CTGAN_AVAILABLE = False
    print("Warning: CTGAN not installed. Using mock generator.")


@dataclass
class GenerationAuditLog:
    """Audit log entry for data generation."""
    generation_id: str
    timestamp: str
    generator_type: str
    input_data_hash: str
    output_data_hash: str
    num_rows_input: int
    num_rows_output: int
    columns: List[str]
    categorical_columns: List[str]
    hyperparameters: Dict
    training_metrics: Dict
    generation_time_seconds: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AuditableCTGAN:
    """
    CTGAN wrapper with comprehensive audit logging.
    
    Features:
    - Automatic hash generation for input/output data
    - Training parameter logging
    - Generation metadata tracking
    - Audit trail export
    """
    
    def __init__(self, epochs: int = 300, batch_size: int = 500,
                 generator_dim: tuple = (256, 256),
                 discriminator_dim: tuple = (256, 256),
                 verbose: bool = True):
        """
        Initialize Auditable CTGAN.
        
        Args:
            epochs: Number of training epochs
            batch_size: Batch size for training
            generator_dim: Generator layer dimensions
            discriminator_dim: Discriminator layer dimensions
            verbose: Whether to print progress
        """
        self.epochs = epochs
        self.batch_size = batch_size
        self.generator_dim = generator_dim
        self.discriminator_dim = discriminator_dim
        self.verbose = verbose
        
        # Initialize CTGAN if available
        if CTGAN_AVAILABLE:
            self.model = CTGAN(
                epochs=epochs,
                batch_size=batch_size,
                generator_dim=generator_dim,
                discriminator_dim=discriminator_dim,
                verbose=verbose
            )
        else:
            self.model = None
        
        # Audit state
        self.audit_logs: List[GenerationAuditLog] = []
        self.is_fitted = False
        self.training_data_hash = None
        self.categorical_columns = []
        self.columns = []
        
        # Training metrics
        self.training_start_time = None
        self.training_end_time = None
        self.loss_history = []
    
    def _compute_hash(self, data: pd.DataFrame) -> str:
        """Compute SHA-256 hash of DataFrame."""
        data_string = data.to_json()
        return hashlib.sha256(data_string.encode()).hexdigest()
    
    def _generate_id(self) -> str:
        """Generate unique ID for generation."""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]
    
    def fit(self, data: pd.DataFrame, 
            discrete_columns: Optional[List[str]] = None) -> 'AuditableCTGAN':
        """
        Fit the CTGAN model with audit logging.
        
        Args:
            data: Training data
            discrete_columns: List of discrete/categorical columns
            
        Returns:
            Self
        """
        import time
        
        self.training_start_time = time.time()
        
        # Store metadata
        self.training_data_hash = self._compute_hash(data)
        self.categorical_columns = discrete_columns or []
        self.columns = list(data.columns)
        
        if self.verbose:
            print(f"Training CTGAN on {len(data)} rows, {len(self.columns)} columns")
            print(f"Input data hash: {self.training_data_hash[:16]}...")
        
        # Fit model
        if CTGAN_AVAILABLE and self.model is not None:
            self.model.fit(data, discrete_columns)
        else:
            # Mock training for testing without CTGAN
            if self.verbose:
                print("Using mock training (CTGAN not available)")
            time.sleep(0.1)  # Simulate training time
        
        self.training_end_time = time.time()
        self.is_fitted = True
        
        training_time = self.training_end_time - self.training_start_time
        
        if self.verbose:
            print(f"Training completed in {training_time:.2f} seconds")
        
        return self
    
    def sample(self, n: int, condition_column: Optional[str] = None,
               condition_value: Optional[Any] = None) -> pd.DataFrame:
        """
        Generate synthetic samples with audit logging.
        
        Args:
            n: Number of samples to generate
            condition_column: Column to condition on
            condition_value: Value to condition on
            
        Returns:
            Synthetic DataFrame
        """
        import time
        
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before sampling")
        
        generation_start = time.time()
        generation_id = self._generate_id()
        
        if self.verbose:
            print(f"Generating {n} synthetic samples...")
            print(f"Generation ID: {generation_id}")
        
        # Generate samples
        if CTGAN_AVAILABLE and self.model is not None:
            if condition_column and condition_value:
                samples = self.model.sample(n, condition_column, condition_value)
            else:
                samples = self.model.sample(n)
        else:
            # Mock generation for testing
            samples = self._mock_generate(n)
        
        generation_end = time.time()
        generation_time = generation_end - generation_start
        
        # Compute output hash
        output_hash = self._compute_hash(samples)
        
        # Create audit log
        audit_log = GenerationAuditLog(
            generation_id=generation_id,
            timestamp=datetime.now().isoformat(),
            generator_type="CTGAN",
            input_data_hash=self.training_data_hash,
            output_data_hash=output_hash,
            num_rows_input=0,  # Not storing input for privacy
            num_rows_output=n,
            columns=self.columns,
            categorical_columns=self.categorical_columns,
            hyperparameters={
                'epochs': self.epochs,
                'batch_size': self.batch_size,
                'generator_dim': list(self.generator_dim),
                'discriminator_dim': list(self.discriminator_dim)
            },
            training_metrics={
                'training_time_seconds': (self.training_end_time - self.training_start_time) 
                                         if self.training_end_time else 0
            },
            generation_time_seconds=generation_time
        )
        
        self.audit_logs.append(audit_log)
        
        if self.verbose:
            print(f"Output data hash: {output_hash[:16]}...")
            print(f"Generation completed in {generation_time:.2f} seconds")
        
        return samples
    
    def _mock_generate(self, n: int) -> pd.DataFrame:
        """Generate mock data when CTGAN is not available."""
        # Generate random data based on column types
        data = {}
        
        for col in self.columns:
            if col in self.categorical_columns:
                # Random categorical values
                categories = [f"{col}_val_{i}" for i in range(5)]
                data[col] = np.random.choice(categories, n)
            else:
                # Random numerical values
                data[col] = np.random.randn(n) * 10 + 50
        
        return pd.DataFrame(data)
    
    def get_audit_logs(self) -> List[Dict]:
        """Get all audit logs."""
        return [log.to_dict() for log in self.audit_logs]
    
    def get_latest_audit_log(self) -> Optional[Dict]:
        """Get the most recent audit log."""
        if self.audit_logs:
            return self.audit_logs[-1].to_dict()
        return None
    
    def export_audit_trail(self, filepath: str) -> None:
        """
        Export audit trail to JSON file.
        
        Args:
            filepath: Path to save audit trail
        """
        audit_data = {
            'generator_info': {
                'type': 'AuditableCTGAN',
                'version': '1.0.0',
                'hyperparameters': {
                    'epochs': self.epochs,
                    'batch_size': self.batch_size,
                    'generator_dim': list(self.generator_dim),
                    'discriminator_dim': list(self.discriminator_dim)
                }
            },
            'training_data_hash': self.training_data_hash,
            'columns': self.columns,
            'categorical_columns': self.categorical_columns,
            'audit_logs': self.get_audit_logs(),
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(audit_data, f, indent=2)
        
        if self.verbose:
            print(f"Audit trail exported to {filepath}")
    
    def verify_generation(self, synthetic_data: pd.DataFrame,
                         generation_id: str) -> Dict:
        """
        Verify that synthetic data matches a generation record.
        
        Args:
            synthetic_data: Data to verify
            generation_id: Generation ID to check against
            
        Returns:
            Verification result
        """
        # Find the audit log
        log = None
        for audit_log in self.audit_logs:
            if audit_log.generation_id == generation_id:
                log = audit_log
                break
        
        if log is None:
            return {
                'verified': False,
                'error': f'Generation ID {generation_id} not found'
            }
        
        # Compute hash of provided data
        data_hash = self._compute_hash(synthetic_data)
        
        # Compare hashes
        matches = data_hash == log.output_data_hash
        
        return {
            'verified': matches,
            'generation_id': generation_id,
            'expected_hash': log.output_data_hash,
            'actual_hash': data_hash,
            'timestamp': log.timestamp,
            'num_rows': log.num_rows_output
        }
    
    def get_generation_metadata(self) -> Dict:
        """Get metadata about all generations."""
        return {
            'total_generations': len(self.audit_logs),
            'total_rows_generated': sum(log.num_rows_output for log in self.audit_logs),
            'training_data_hash': self.training_data_hash,
            'model_hyperparameters': {
                'epochs': self.epochs,
                'batch_size': self.batch_size,
                'generator_dim': list(self.generator_dim),
                'discriminator_dim': list(self.discriminator_dim)
            },
            'generations': [
                {
                    'id': log.generation_id,
                    'timestamp': log.timestamp,
                    'rows': log.num_rows_output,
                    'hash': log.output_data_hash[:16] + '...'
                }
                for log in self.audit_logs
            ]
        }

    def save(self, filepath: str) -> None:
        """
        Save the trained model to a file.
        
        Args:
            filepath: Path to save the model
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before saving")
        
        # Save CTGAN model separately using its native method
        model_path = filepath.replace('.pkl', '_ctgan.pkl')
        if self.model is not None:
            self.model.save(model_path)
        
        # Save metadata separately
        metadata = {
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'generator_dim': self.generator_dim,
            'discriminator_dim': self.discriminator_dim,
            'is_fitted': self.is_fitted,
            'training_data_hash': self.training_data_hash,
            'categorical_columns': self.categorical_columns,
            'columns': self.columns,
            'training_start_time': self.training_start_time,
            'training_end_time': self.training_end_time,
            'audit_logs': [log.to_dict() if hasattr(log, 'to_dict') else log for log in self.audit_logs],
            'ctgan_model_path': model_path
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(metadata, f)
        
        if self.verbose:
            print(f"Model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str, verbose: bool = True) -> 'AuditableCTGAN':
        """
        Load a trained model from a file.
        
        Args:
            filepath: Path to the saved model
            verbose: Whether to print progress
            
        Returns:
            Loaded AuditableCTGAN instance
        """
        with open(filepath, 'rb') as f:
            metadata = pickle.load(f)
        
        # Validate that loaded data is a dictionary
        if not isinstance(metadata, dict):
            raise ValueError(f"Invalid cache file format. Expected dict, got {type(metadata).__name__}. Delete the cache file and retrain.")
        
        instance = cls(
            epochs=metadata['epochs'],
            batch_size=metadata['batch_size'],
            generator_dim=metadata['generator_dim'],
            discriminator_dim=metadata['discriminator_dim'],
            verbose=verbose
        )
        
        instance.is_fitted = metadata['is_fitted']
        instance.training_data_hash = metadata['training_data_hash']
        instance.categorical_columns = metadata['categorical_columns']
        instance.columns = metadata['columns']
        instance.training_start_time = metadata['training_start_time']
        instance.training_end_time = metadata['training_end_time']
        instance.audit_logs = metadata['audit_logs']
        
        # Load CTGAN model using its native method
        ctgan_path = metadata.get('ctgan_model_path', filepath.replace('.pkl', '_ctgan.pkl'))
        if CTGAN_AVAILABLE and os.path.exists(ctgan_path):
            instance.model = CTGAN.load(ctgan_path)
        
        if verbose:
            print(f"Model loaded from {filepath}")
        
        return instance


# Convenience function
def generate_auditable_synthetic_data(
    real_data: pd.DataFrame,
    discrete_columns: Optional[List[str]] = None,
    n_samples: Optional[int] = None,
    epochs: int = 200,
    verbose: bool = True
) -> tuple:
    """
    Generate synthetic data with full audit trail.
    
    Args:
        real_data: Original training data
        discrete_columns: List of categorical columns
        n_samples: Number of samples (default: same as input)
        epochs: Training epochs
        verbose: Print progress
        
    Returns:
        Tuple of (synthetic_data, audit_log)
    """
    n_samples = n_samples or len(real_data)
    
    generator = AuditableCTGAN(epochs=epochs, verbose=verbose)
    generator.fit(real_data, discrete_columns)
    synthetic_data = generator.sample(n_samples)
    
    return synthetic_data, generator.get_latest_audit_log()
