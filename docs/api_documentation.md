# API Documentation

## Blockchain-Based Audit Trails for Synthetic Data Generation

### Overview

This document describes the API endpoints and modules available in the verification system.

---

## Table of Contents

1. [Main Pipeline](#main-pipeline)
2. [Audit System Modules](#audit-system-modules)
3. [Blockchain API](#blockchain-api)
4. [Dashboard API](#dashboard-api)
5. [Data Generators](#data-generators)

---

## Main Pipeline

### `SyntheticDataVerificationPipeline`

The main orchestrator for the verification workflow.

```python
from main_verification_pipeline import SyntheticDataVerificationPipeline

pipeline = SyntheticDataVerificationPipeline(
    blockchain_mode="simulation",  # or "fabric"
    threshold=70.0
)
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `run_full_pipeline()` | `real_data_path`, `synthetic_data_path`, `generate_synthetic` | `Dict` | Run complete verification |
| `_generate_synthetic_data()` | `real_data`, `model_path` | `Tuple[DataFrame, AuditableCTGAN]` | Generate synthetic data |
| `_run_privacy_verification()` | `real_data`, `synthetic_data` | `Dict` | Run privacy checks |
| `_run_utility_verification()` | `real_data`, `synthetic_data` | `Dict` | Run utility checks |
| `_run_bias_detection()` | `real_data`, `synthetic_data` | `Dict` | Run fairness checks |
| `_run_consensus()` | `verification_results` | `ConsensusRecord` | Aggregate results |

#### CLI Usage

```bash
# Generate synthetic data and verify
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --threshold 70

# Use existing synthetic data
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --synthetic-data data/raw/synthetic_adult.csv \
    --threshold 70

# Force retraining (ignore cache)
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --no-cache
```

---

## Audit System Modules

### `PrivacyVerifier`

Evaluates privacy metrics of synthetic data.

```python
from audit_system.privacy_verifier import PrivacyVerifier

verifier = PrivacyVerifier(real_data, synthetic_data)
results = verifier.verify_all()
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `verify_all()` | `Dict` | Run all privacy checks |
| `compute_dcr()` | `Dict` | Distance to Closest Record |
| `compute_k_anonymity()` | `Dict` | k-Anonymity check |
| `compute_membership_inference()` | `Dict` | MIA vulnerability test |
| `compute_attribute_disclosure()` | `Dict` | Attribute disclosure risk |

#### Response Format

```json
{
  "privacy_score": 54.73,
  "dcr": {"mean_dcr": 0.12, "min_dcr": 0.05, "passed": true},
  "k_anonymity": {"k_value": 5, "passed": true},
  "membership_inference": {"accuracy": 0.53, "passed": true},
  "attribute_disclosure": {"risk_score": 0.15, "passed": true}
}
```

---

### `UtilityVerifier`

Evaluates utility/usefulness of synthetic data.

```python
from audit_system.utility_verifier import UtilityVerifier

verifier = UtilityVerifier(real_data, synthetic_data)
results = verifier.verify_all()
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `verify_all()` | `Dict` | Run all utility checks |
| `compute_statistical_similarity()` | `Dict` | Wasserstein distance |
| `compute_correlation_preservation()` | `Dict` | Correlation matrix difference |
| `compute_ml_efficacy()` | `Dict` | Train-on-Synthetic, Test-on-Real |

#### Response Format

```json
{
  "utility_score": 74.57,
  "statistical_similarity": {"wasserstein_distance": 0.08, "passed": true},
  "correlation_preservation": {"mean_diff": 0.05, "passed": true},
  "ml_efficacy": {"tstr_accuracy": 0.78, "trtr_accuracy": 0.82, "ratio": 0.95}
}
```

---

### `BiasDetector`

Evaluates fairness metrics across protected attributes.

```python
from audit_system.bias_detector import BiasDetector

detector = BiasDetector(
    real_data, 
    synthetic_data,
    protected_attributes=['sex', 'race'],
    target_column='income'
)
results = detector.detect_all()
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `detect_all()` | `Dict` | Run all bias checks |
| `compute_demographic_parity()` | `Dict` | Distribution equality |
| `compute_disparate_impact()` | `Dict` | 80% rule check |
| `compute_equal_opportunity()` | `Dict` | TPR equality |

---

### `ConsensusEngine`

Aggregates verification results from multiple verifiers.

```python
from audit_system.consensus_engine import ConsensusEngine

engine = ConsensusEngine(num_verifiers=3, threshold=70.0)
engine.create_verification_request(data_hash)
engine.submit_verification(data_hash, verifier_id, scores)
consensus = engine.get_consensus(data_hash)
```

#### Methods

| Method | Parameters | Returns |
|--------|------------|---------|
| `create_verification_request()` | `data_hash` | `bool` |
| `submit_verification()` | `data_hash`, `verifier_id`, `scores` | `bool` |
| `get_consensus()` | `data_hash` | `ConsensusRecord` |

---

### `ComplianceChecker`

Checks regulatory compliance (GDPR, HIPAA, EU AI Act).

```python
from audit_system.compliance_checker import ComplianceChecker

checker = ComplianceChecker(verification_results)
compliance = checker.check_all()
```

---

## Blockchain API

### `BlockchainClient`

Interface to blockchain backend (simulation or Hyperledger Fabric).

```python
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode

client = BlockchainClient(mode=BlockchainMode.SIMULATION)
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `log_verification()` | `data_hash`, `verification_id`, `results` | `str` | Log verification to chain |
| `get_verification()` | `data_hash` | `Dict` | Retrieve verification record |
| `get_blockchain_stats()` | - | `Dict` | Get chain statistics |

#### Helper Functions

```python
from blockchain.api.blockchain_client import compute_data_hash

# Compute deterministic hash of DataFrame
data_hash = compute_data_hash(df)
```

---

## Dashboard API

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard home page |
| `/api/verify` | POST | Submit data for verification |
| `/api/status/<job_id>` | GET | Check verification status |
| `/api/audit-trail` | GET | List all audit records |
| `/api/report/<data_hash>` | GET | Get verification report |

### Running the Dashboard

```bash
cd dashboard
python app.py
# Access at http://localhost:5000
```

---

## Data Generators

### `AuditableCTGAN`

CTGAN wrapper with audit logging.

```python
from ml_models.generators.auditable_ctgan import AuditableCTGAN

generator = AuditableCTGAN(epochs=100, verbose=True)
generator.fit(real_data, discrete_columns=['sex', 'race', 'income'])
synthetic_data = generator.sample(n_samples=10000)

# Save/load model
generator.save('model.pkl')
loaded = AuditableCTGAN.load('model.pkl')
```

### `AuditableVAE`

VAE-based generator with audit logging.

```python
from ml_models.generators.vae_generator import AuditableVAE

generator = AuditableVAE(latent_dim=32, epochs=100)
generator.fit(real_data)
synthetic_data = generator.sample(n_samples=10000)
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `E001` | Invalid data format |
| `E002` | Verification failed |
| `E003` | Blockchain connection error |
| `E004` | Consensus not reached |
| `E005` | Compliance check failed |

---

## Configuration

### Environment Variables

```bash
# .env file
BLOCKCHAIN_MODE=simulation
VERIFICATION_THRESHOLD=70
NUM_VERIFIERS=3
LOG_LEVEL=INFO
```

---

## Examples

### Complete Verification Workflow

```python
import pandas as pd
from main_verification_pipeline import SyntheticDataVerificationPipeline

# Load data
real_data = pd.read_csv('data/raw/adult.csv')

# Initialize pipeline
pipeline = SyntheticDataVerificationPipeline(
    blockchain_mode='simulation',
    threshold=70.0
)

# Run verification
results = pipeline.run_full_pipeline(
    real_data_path='data/raw/adult.csv',
    generate_synthetic=True
)

print(f"Overall Score: {results['overall_score']}")
print(f"Status: {results['status']}")
```

### Standalone Privacy Check

```python
import pandas as pd
from audit_system.privacy_verifier import PrivacyVerifier

real = pd.read_csv('real_data.csv')
synthetic = pd.read_csv('synthetic_data.csv')

verifier = PrivacyVerifier(real, synthetic)
results = verifier.verify_all()

print(f"Privacy Score: {results['privacy_score']}")
print(f"DCR Passed: {results['dcr']['passed']}")
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-17 | Initial release |

---

## Support

For issues or questions, please open an issue on GitHub or contact the development team.
