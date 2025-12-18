"""
Train CTGAN models for all datasets in data/raw folder.
Run this script once to pre-train and cache all models.
Subsequent pipeline runs will load from cache (fast!).
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from ml_models.generators.auditable_ctgan import AuditableCTGAN

# Configuration for each dataset
DATASETS = {
    'adult': {
        'path': 'data/raw/adult.csv',
        'cache_path': 'results/cached_ctgan_adult.pkl',
        'epochs': 100,
        'categorical_columns': None,  # Auto-detect
        'drop_columns': [],  # No columns to drop
        'sample_size': None  # Use full dataset
    },
    'healthcare': {
        'path': 'data/raw/healthcare_dataset.csv',
        'cache_path': 'results/cached_ctgan_healthcare.pkl',
        'epochs': 100,
        'categorical_columns': None,  # Auto-detect
        # Drop high-cardinality columns to prevent memory issues
        # These columns have thousands of unique values (Name, Doctor, Hospital)
        'drop_columns': ['Name', 'Doctor', 'Hospital'],
        'sample_size': 10000  # Sample to reduce memory usage
    }
}


def auto_detect_categorical(df, threshold=20):
    """Auto-detect categorical columns."""
    categorical = []
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].nunique() < threshold:
            categorical.append(col)
    return categorical


def train_model(name, config, force_retrain=False):
    """Train and cache a model for a dataset."""
    cache_path = config['cache_path']
    ctgan_cache_path = cache_path.replace('.pkl', '_ctgan.pkl')
    
    # Check if already cached
    if not force_retrain and os.path.exists(cache_path) and os.path.exists(ctgan_cache_path):
        print(f"\n[{name.upper()}] Model already cached at: {cache_path}")
        print(f"[{name.upper()}] Skipping training. Use --force to retrain.")
        return True
    
    print(f"\n{'='*60}")
    print(f"TRAINING MODEL: {name.upper()}")
    print(f"{'='*60}")
    
    # Load data
    print(f"[{name.upper()}] Loading data from: {config['path']}")
    df = pd.read_csv(config['path'])
    print(f"[{name.upper()}] Original data shape: {df.shape}")
    
    # Drop high-cardinality columns if specified
    drop_columns = config.get('drop_columns', [])
    if drop_columns:
        df = df.drop(columns=[c for c in drop_columns if c in df.columns])
        print(f"[{name.upper()}] Dropped columns: {drop_columns}")
        print(f"[{name.upper()}] New data shape: {df.shape}")
    
    # Sample data if specified (to reduce memory usage)
    sample_size = config.get('sample_size')
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)
        print(f"[{name.upper()}] Sampled {sample_size} rows for training")
    
    # Detect categorical columns
    categorical = config['categorical_columns'] or auto_detect_categorical(df)
    # Remove any dropped columns from categorical list
    categorical = [c for c in categorical if c in df.columns]
    print(f"[{name.upper()}] Categorical columns ({len(categorical)}): {categorical}")
    
    # Create and train model
    print(f"[{name.upper()}] Training CTGAN with {config['epochs']} epochs...")
    print(f"[{name.upper()}] This may take several minutes...")
    
    generator = AuditableCTGAN(
        epochs=config['epochs'],
        batch_size=500,
        verbose=True
    )
    
    generator.fit(df, discrete_columns=categorical)
    
    # Save model
    generator.save(cache_path)
    print(f"\n[{name.upper()}] Model saved to: {cache_path}")
    print(f"[{name.upper()}] Training complete!")
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Train CTGAN models for all datasets')
    parser.add_argument('--force', action='store_true', help='Force retrain all models')
    parser.add_argument('--dataset', type=str, choices=['adult', 'healthcare', 'all'], 
                        default='all', help='Which dataset to train')
    args = parser.parse_args()
    
    print("="*60)
    print("CTGAN MODEL TRAINING SCRIPT")
    print("="*60)
    print(f"This script trains and caches CTGAN models for faster pipeline runs.")
    print(f"Once trained, the pipeline will load from cache instead of retraining.\n")
    
    # Ensure results directory exists
    Path("results").mkdir(exist_ok=True)
    
    # Train selected models
    datasets_to_train = DATASETS.keys() if args.dataset == 'all' else [args.dataset]
    
    for name in datasets_to_train:
        if name in DATASETS:
            try:
                train_model(name, DATASETS[name], force_retrain=args.force)
            except Exception as e:
                print(f"\n[{name.upper()}] ERROR: {e}")
                continue
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE!")
    print("="*60)
    print("\nCached models:")
    for name, config in DATASETS.items():
        cache_path = config['cache_path']
        if os.path.exists(cache_path):
            size = os.path.getsize(cache_path) / 1024
            print(f"  ✓ {name}: {cache_path} ({size:.1f} KB)")
        else:
            print(f"  ✗ {name}: Not trained yet")
    
    print("\nUsage:")
    print("  # Run pipeline with adult dataset (uses cache)")
    print("  python main_verification_pipeline.py --real-data data/raw/adult.csv --generate")
    print()
    print("  # Run pipeline with healthcare dataset (uses cache)")
    print("  python main_verification_pipeline.py --real-data data/raw/healthcare_dataset.csv --generate")


if __name__ == "__main__":
    main()
