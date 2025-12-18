# Blockchain-Based Audit Trails for Synthetic Data Generation

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Hyperledger Fabric 2.5](https://img.shields.io/badge/Fabric-2.5-green.svg)](https://hyperledger-fabric.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive framework for creating verifiable and trustworthy synthetic data with blockchain-based audit trails. This project addresses the critical need for transparency and accountability in synthetic data generation, particularly for sensitive domains like healthcare and finance.

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This project implements a **two-layer security model** for synthetic data:

1. **Layer 1 - Verification System**: Validates synthetic data quality through:
   - Privacy metrics (DCR, k-anonymity, membership inference)
   - Utility metrics (statistical similarity, ML efficacy)
   - Fairness metrics (demographic parity, disparate impact)

2. **Layer 2 - Blockchain**: Provides immutable audit trails for:
   - Data generation events
   - Verification results
   - Consensus outcomes
   - Compliance attestations

## ✨ Key Features

- **Auditable CTGAN Generator**: Synthetic data generation with built-in audit logging
- **Comprehensive Verification**: Privacy, utility, and fairness verification modules
- **Distributed Consensus**: Multi-peer verification with Byzantine fault tolerance
- **Hyperledger Fabric Integration**: Enterprise-grade blockchain for audit trails
- **Regulatory Compliance**: GDPR, HIPAA, and EU AI Act compliance checking
- **Interactive Dashboard**: Web-based monitoring and verification interface
- **Rust Chaincode**: High-performance smart contracts in Rust

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER/RESEARCHER LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Generator   │  │   Auditor    │  │  Regulator   │          │
│  │   Portal     │  │   Dashboard  │  │   Portal     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VERIFICATION ENGINE                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Privacy    │  │   Utility    │  │   Fairness   │          │
│  │   Verifier   │  │   Verifier   │  │   Detector   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  Compliance  │  │  Consensus   │                            │
│  │   Checker    │  │   Engine     │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              BLOCKCHAIN LAYER (Hyperledger Fabric)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Hospital   │  │  Regulator  │  │  Research   │             │
│  │    Peer     │  │    Peer     │  │    Peer     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│         └─────────────────┴─────────────────┘                   │
│                    Immutable Ledger                             │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose
- Rust (for chaincode compilation)
- Hyperledger Fabric 2.5 binaries (optional, for production)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/FY-Project.git
cd FY-Project
```

### Step 2: Create Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
```

### Step 5: (Optional) Start Fabric Network

For production use with Hyperledger Fabric:

```bash
cd blockchain/network
chmod +x setup_network.sh
./setup_network.sh start
```

## ⚡ Quick Start

### Basic Usage (Simulation Mode)

```python
from main_verification_pipeline import VerificationPipeline

# Initialize pipeline
pipeline = VerificationPipeline(
    num_verifiers=3,
    approval_threshold=70.0
)

# Load data and generate synthetic data
pipeline.load_data(
    real_data_path="data/raw/adult.csv",
    generate_synthetic=True,
    categorical_columns=['workclass', 'education', 'occupation', 'income']
)

# Run verification
results = pipeline.run_verification()

# Generate report
report = pipeline.generate_report()
print(f"Overall Score: {report['overall_score']}")
print(f"Status: {report['status']}")
```

### Command Line Interface

```bash
# Generate and verify synthetic data
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --threshold 70

# Verify existing synthetic data
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --synthetic-data data/synthetic/synthetic_adult.csv \
    --threshold 70
```

### Start Dashboard

```bash
cd dashboard
python app.py
# Open http://localhost:5000 in your browser
```

## 📁 Project Structure

```
FY-Project/
├── audit_system/               # Verification modules
│   ├── privacy_verifier.py     # Privacy metrics (DCR, k-anonymity)
│   ├── utility_verifier.py     # Utility metrics (Wasserstein, ML)
│   ├── bias_detector.py        # Fairness metrics
│   ├── compliance_checker.py   # Regulatory compliance
│   ├── consensus_engine.py     # Multi-peer consensus
│   └── logger.py               # Audit logging
│
├── blockchain/
│   ├── api/
│   │   ├── blockchain_client.py        # Python SDK wrapper
│   │   └── verification_orchestrator.py # Distributed verification
│   ├── chaincode/
│   │   ├── audit_trail.go              # Go chaincode
│   │   └── rust/                       # Rust chaincode
│   │       ├── Cargo.toml
│   │       └── src/lib.rs
│   └── network/
│       ├── docker-compose.yaml         # Fabric network config
│       ├── configtx.yaml              # Channel configuration
│       ├── crypto-config.yaml         # Certificate setup
│       └── setup_network.sh           # Network setup script
│
├── dashboard/
│   ├── app.py                  # Flask application
│   └── templates/
│       └── index.html          # Dashboard UI
│
├── data/
│   ├── raw/                    # Original datasets
│   └── synthetic/              # Generated synthetic data
│
├── docs/
│   ├── api_documentation.md    # API reference
│   ├── blockchain_documentation.md  # Blockchain guide
│   └── research_paper/         # LaTeX paper
│
├── experiments/
│   ├── comparative_study.py    # Baseline comparisons
│   ├── scalability_test.py     # Performance testing
│   └── ablation_study.py       # Feature importance
│
├── ml_models/
│   └── generators/
│       ├── auditable_ctgan.py  # Auditable CTGAN
│       └── vae_generator.py    # VAE alternative
│
├── results/
│   ├── experiments/            # Experimental results
│   ├── metrics/                # Verification metrics
│   ├── plots/                  # Generated figures
│   └── reports/                # Compliance reports
│
├── tests/                      # Unit and integration tests
├── main_verification_pipeline.py  # Main entry point
└── requirements.txt            # Python dependencies
```

## 📖 Usage

### Verification Modules

#### Privacy Verification

```python
from audit_system.privacy_verifier import PrivacyVerifier

verifier = PrivacyVerifier(real_data, synthetic_data)
results = verifier.verify_all()

print(f"Privacy Score: {results['overall']['privacy_score']}")
print(f"DCR: {results['dcr']['mean_dcr']}")
print(f"k-Anonymity: {results['k_anonymity']['achieved_k']}")
```

#### Utility Verification

```python
from audit_system.utility_verifier import UtilityVerifier

verifier = UtilityVerifier(real_data, synthetic_data)
results = verifier.verify_all()

print(f"Utility Score: {results['overall']['utility_score']}")
print(f"Statistical Similarity: {results['statistical']['similarity_score']}")
```

#### Fairness Detection

```python
from audit_system.bias_detector import BiasDetector

detector = BiasDetector(
    real_data, 
    synthetic_data,
    protected_attribute='gender',
    target_column='income'
)
results = detector.verify_all()

print(f"Fairness Score: {results['overall']['fairness_score']}")
```

### Blockchain Operations

```python
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode

# Simulation mode (development)
client = BlockchainClient(mode=BlockchainMode.SIMULATION)

# Fabric mode (production)
client = BlockchainClient(
    mode=BlockchainMode.FABRIC,
    config={
        'peer_endpoint': 'localhost:7051',
        'channel_name': 'auditchannel',
        'chaincode_name': 'audit_trail'
    }
)

# Log generation
entry_id = client.log_generation(
    data_hash="abc123...",
    generator_type="CTGAN",
    parameters={"epochs": 100, "batch_size": 500}
)

# Get audit trail
trail = client.get_audit_trail(data_hash)
```

## 📚 API Documentation

See [docs/api_documentation.md](docs/api_documentation.md) for complete API reference.

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Modules

```bash
# Privacy tests
pytest tests/test_privacy.py -v

# Integration tests
pytest tests/test_integration.py -v

# Compliance tests
pytest tests/test_compliance.py -v
```

### Run Experiments

```bash
# Comparative study
python experiments/comparative_study.py

# Scalability tests
python experiments/scalability_test.py
```

## 📊 Experimental Results

Our experiments demonstrate:

- **Privacy**: Average DCR of 0.15+ across datasets
- **Utility**: >85% ML efficacy compared to real data
- **Fairness**: Demographic parity within 10% threshold
- **Performance**: <5s verification for 10K rows
- **Scalability**: Linear scaling up to 50K rows

See `results/experiments/` for detailed results.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

- **Author**: Ashish Pandey
- **Email**: your.email@example.com
- **Project Link**: https://github.com/yourusername/FY-Project

## 🙏 Acknowledgments

- Hyperledger Fabric community
- SDV (Synthetic Data Vault) team
- UCI Machine Learning Repository for datasets

---

**Built with ❤️ for trustworthy synthetic data generation**
