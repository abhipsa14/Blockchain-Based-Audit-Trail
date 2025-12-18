# Setup Guide - Blockchain-Based Audit Trails for Synthetic Data

This guide provides detailed instructions for setting up the project in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Setup](#development-setup)
3. [Hyperledger Fabric Setup](#hyperledger-fabric-setup)
4. [Rust Chaincode Compilation](#rust-chaincode-compilation)
5. [Dashboard Setup](#dashboard-setup)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Main application |
| Docker | 20.10+ | Containerization |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Rust | 1.70+ | Chaincode development |
| Git | 2.30+ | Version control |

### Optional Software

| Software | Version | Purpose |
|----------|---------|---------|
| Hyperledger Fabric | 2.5 | Production blockchain |
| Go | 1.20+ | Alternative chaincode |
| Node.js | 18+ | Fabric SDK |

---

## Development Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/FY-Project.git
cd FY-Project
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.venv\Scripts\activate.bat

# Activate (Linux/macOS)
source .venv/bin/activate
```

### Step 3: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check module imports
python -c "from audit_system.privacy_verifier import PrivacyVerifier; print('OK')"
python -c "from blockchain.api.blockchain_client import BlockchainClient; print('OK')"
```

### Step 5: Configure Environment

Create a `.env` file:

```bash
# Copy example
cp .env.example .env

# Or create manually
cat > .env << EOF
# Blockchain Configuration
BLOCKCHAIN_MODE=simulation
FABRIC_PEER_ENDPOINT=localhost:7051
FABRIC_ORDERER_ENDPOINT=localhost:7050
FABRIC_CHANNEL_NAME=auditchannel
FABRIC_CHAINCODE_NAME=audit_trail

# Verification Settings
DEFAULT_APPROVAL_THRESHOLD=70
MIN_VERIFIERS=3
MAX_VERIFIERS=7

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs

# Dashboard
FLASK_DEBUG=true
FLASK_PORT=5000
EOF
```

---

## Hyperledger Fabric Setup

### Option A: Using Docker (Recommended for Development)

#### Step 1: Install Fabric Binaries

```bash
# Download Fabric samples and binaries
curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.0 1.5.6

# Add to PATH (Linux/macOS)
export PATH=$PWD/fabric-samples/bin:$PATH

# Add to PATH (Windows PowerShell)
$env:PATH = "$PWD\fabric-samples\bin;$env:PATH"
```

#### Step 2: Start the Network

```bash
cd blockchain/network

# Make script executable (Linux/macOS)
chmod +x setup_network.sh

# Start network
./setup_network.sh start
```

#### Step 3: Verify Network

```bash
# Check running containers
docker ps

# Expected containers:
# - orderer.audit.com
# - peer0.hospital.audit.com
# - peer0.regulator.audit.com
# - peer0.research.audit.com
# - ca.hospital.audit.com
# - ca.regulator.audit.com
# - ca.research.audit.com
```

### Option B: Simulation Mode (No Docker Required)

For development without Docker, use simulation mode:

```python
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode

# Uses in-memory simulated blockchain
client = BlockchainClient(mode=BlockchainMode.SIMULATION)
```

---

## Rust Chaincode Compilation

### Step 1: Install Rust

```bash
# Linux/macOS
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Windows
# Download from https://rustup.rs/
```

### Step 2: Configure Rust Toolchain

```bash
# Add WebAssembly target (for Fabric)
rustup target add wasm32-unknown-unknown

# Verify installation
rustc --version
cargo --version
```

### Step 3: Build Chaincode

```bash
cd blockchain/chaincode/rust

# Build in release mode
cargo build --release

# Run tests
cargo test
```

### Step 4: Package for Fabric

```bash
# Create chaincode package
tar -czvf audit_trail_rust.tar.gz \
    -C target/release \
    libaudit_trail.so
```

---

## Dashboard Setup

### Step 1: Install Dashboard Dependencies

```bash
pip install flask flask-cors
```

### Step 2: Start Dashboard

```bash
cd dashboard
python app.py
```

### Step 3: Access Dashboard

Open your browser and navigate to:
- **Local**: http://localhost:5000
- **Network**: http://<your-ip>:5000

### Dashboard Features

- **Data Upload**: Upload CSV files for verification
- **Real-time Verification**: Monitor verification progress
- **Audit Trail Explorer**: Browse blockchain records
- **Report Generation**: Download compliance reports

---

## Running the Full Pipeline

### Basic Verification

```bash
# Generate synthetic data and verify
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --threshold 70
```

### With Existing Synthetic Data

```bash
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --synthetic-data data/synthetic/synthetic_adult.csv \
    --threshold 70
```

### Production Mode (with Fabric)

```bash
# Set environment variable
export BLOCKCHAIN_MODE=fabric

# Run pipeline
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --threshold 70
```

---

## Troubleshooting

### Common Issues

#### 1. Python Import Errors

```
ModuleNotFoundError: No module named 'sdv'
```

**Solution**: Install missing dependencies
```bash
pip install sdv ctgan
```

#### 2. Docker Connection Refused

```
Error: Cannot connect to Docker daemon
```

**Solution**: Start Docker Desktop or Docker daemon
```bash
# Linux
sudo systemctl start docker

# Windows/macOS
# Start Docker Desktop application
```

#### 3. Fabric Network Issues

```
Error: endorsement failure during invoke
```

**Solution**: Check peer logs
```bash
docker logs peer0.hospital.audit.com
```

#### 4. Permission Denied (Linux)

```
Permission denied: /var/run/docker.sock
```

**Solution**: Add user to docker group
```bash
sudo usermod -aG docker $USER
newgrp docker
```

#### 5. Rust Compilation Errors

```
error[E0425]: cannot find value
```

**Solution**: Update dependencies
```bash
cd blockchain/chaincode/rust
cargo update
cargo build --release
```

### Getting Help

1. Check the [FAQ](docs/faq.md)
2. Search existing [Issues](https://github.com/yourusername/FY-Project/issues)
3. Open a new issue with:
   - OS and version
   - Python version
   - Error message
   - Steps to reproduce

---

## Next Steps

After setup, explore:

1. **[API Documentation](docs/api_documentation.md)** - Complete API reference
2. **[Blockchain Documentation](docs/blockchain_documentation.md)** - Blockchain integration guide
3. **[Examples](examples/)** - Sample code and notebooks
4. **[Experiments](experiments/)** - Run comparative studies

---

**Happy coding! 🚀**
