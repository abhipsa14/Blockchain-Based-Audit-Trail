# 🚀 Run Instructions - Synthetic Data Verification System

This guide provides step-by-step instructions to set up and run the Blockchain-Based Synthetic Data Verification System.

---

## 📋 Prerequisites

Before running the project, ensure you have the following installed:

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Core runtime |
| pip | Latest | Package management |
| Git | Latest | Version control |
| Docker | Latest | Blockchain network (optional) |

---

## 🛠️ Initial Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/FY-Project.git
cd FY-Project
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation

```bash
python -c "import pandas, numpy, flask, sdv; print('All dependencies installed successfully!')"
```

---

## 🎯 Running the Project

### Option 1: Web Dashboard (Recommended)

The easiest way to use the system is through the web dashboard.

```bash
python dashboard/app.py
```

Then open your browser and navigate to:
```
http://127.0.0.1:5000
```

**Dashboard Features:**
- Upload real and synthetic datasets (CSV)
- Generate synthetic data using CTGAN
- Run distributed verification
- View compliance reports (GDPR, HIPAA, EU AI Act)
- Download verification reports (JSON/PDF)

---

### Option 2: Command Line Pipeline

Run verification from the command line:

**Generate synthetic data and verify:**
```bash
python main_verification_pipeline.py --real-data data/raw/adult.csv --generate --threshold 70
```

**Verify existing synthetic data:**
```bash
python main_verification_pipeline.py --real-data data/raw/adult.csv --synthetic-data data/synthetic/synthetic_adult.csv --threshold 70
```

**Full options:**
```bash
python main_verification_pipeline.py --help
```

| Argument | Description | Default |
|----------|-------------|---------|
| `--real-data` | Path to real dataset (CSV) | Required |
| `--synthetic-data` | Path to synthetic dataset | None (generates new) |
| `--generate` | Generate synthetic data | False |
| `--threshold` | Approval threshold (0-100) | 70 |
| `--num-verifiers` | Number of verifiers | 3 |
| `--output-dir` | Output directory | results/ |

---

### Option 3: Train Models Separately

Pre-train CTGAN models for faster verification:

```bash
python train_all_models.py
```

This will train models on all datasets in `data/raw/` and cache them in `results/`.

---

## 📊 Using the Dashboard

### Step-by-Step Guide:

1. **Start the Dashboard**
   ```bash
   python dashboard/app.py
   ```

2. **Select Mode:**
   - **Generate & Verify**: Upload real data → Generate synthetic → Verify
   - **Upload Both**: Upload both real and synthetic data → Verify
   - **Synthetic Only**: Analyze synthetic data quality without real data

3. **Upload Data:**
   - Click on the upload zones to select CSV files
   - Example: `data/raw/adult.csv`

4. **Configure Columns:**
   - **Categorical Columns**: `workclass, education, occupation, sex, race, marital.status, relationship, native.country, income`
   - **Protected Attributes**: `sex, race` (for bias detection)
   - **Target Column**: `income` (for ML efficacy tests)

5. **Set Parameters:**
   - **Number of Verifiers**: 3-7 (more = more thorough)
   - **Approval Threshold**: 60-80% (higher = stricter)

6. **Run Verification:**
   - Click "Run Verification"
   - Wait for results (typically 10-30 seconds)

7. **View Results:**
   - Privacy Score (Target: ≥70%)
   - Utility Score (Target: ≥70%)
   - Fairness Score (Target: ≥80%)
   - Overall Score (Target: ≥70%)
   - Compliance Status (GDPR, HIPAA, EU AI Act)

8. **Download Reports:**
   - JSON Report: Detailed machine-readable format
   - PDF Report: Human-readable summary

---

## 🧪 Running Tests

### Run All Tests:
```bash
pytest tests/ -v
```

### Run Specific Test Categories:
```bash
# Privacy tests
pytest tests/test_privacy.py -v

# Utility tests
pytest tests/test_utility.py -v

# Consensus tests
pytest tests/test_consensus.py -v

# Compliance tests
pytest tests/test_compliance.py -v

# Integration tests
pytest tests/test_integration.py -v
```

### Run with Coverage:
```bash
pytest tests/ --cov=audit_system --cov-report=html
```

---

## 📈 Running Experiments

### Comparative Study (Benchmark)
```bash
python -c "from experiments import run_comparative_study; run_comparative_study()"
```

### Scalability Test
```bash
python -c "from experiments import run_scalability_test; run_scalability_test()"
```

### Ablation Study
```bash
python -c "from experiments import run_ablation_study; run_ablation_study()"
```

Results will be saved to `results/experiments/`.

---

## ⛓️ Blockchain Network (Optional)

To run with a real Hyperledger Fabric network:

### Prerequisites:
- Docker & Docker Compose
- Hyperledger Fabric binaries

### Start Network:
```bash
cd blockchain/network
chmod +x setup_network.sh
./setup_network.sh
```

### Start with Docker:
```bash
docker-compose up -d
```

### Stop Network:
```bash
docker-compose down
```

> **Note:** The system works in simulation mode by default. Blockchain network is optional for production deployments.

---

## 📁 Sample Datasets

The project includes sample datasets:

| Dataset | Path | Rows | Columns | Domain |
|---------|------|------|---------|--------|
| Adult Census | `data/raw/adult.csv` | 32,561 | 15 | Demographics |
| Healthcare | `data/raw/healthcare_dataset.csv` | 55,500 | 15 | Healthcare |

### Using Your Own Data:

1. Place your CSV file in `data/raw/`
2. Ensure it has a header row
3. Identify categorical vs numerical columns
4. Run verification with appropriate column settings

---

## 🔧 Configuration

### Environment Variables (.env):
```env
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-secret-key
BLOCKCHAIN_MODE=simulation
```

### Verification Thresholds:
| Metric | Default Threshold | Description |
|--------|-------------------|-------------|
| Privacy | ≥70% | DCR, k-anonymity, membership inference |
| Utility | ≥70% | Statistical similarity, ML efficacy |
| Fairness | ≥80% | Demographic parity, equalized odds |
| Overall | ≥70% | Weighted average (40% P + 35% U + 25% F) |

---

## 🐛 Troubleshooting

### Common Issues:

**1. ModuleNotFoundError:**
```bash
# Ensure virtual environment is activated
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # Linux/macOS

# Reinstall dependencies
pip install -r requirements.txt
```

**2. Port Already in Use:**
```bash
# Find and kill process on port 5000
# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/macOS:
lsof -i :5000
kill -9 <PID>
```

**3. Memory Error During Training:**
```bash
# Use smaller dataset sample
python main_verification_pipeline.py --real-data data/raw/adult.csv --generate --sample-size 10000
```

**4. CTGAN Training Slow:**
```bash
# Use cached model (if available)
# Models are cached in results/cached_ctgan_*.pkl
```

**5. Dashboard Not Loading:**
```bash
# Check Flask is running
python dashboard/app.py

# Check for errors in terminal output
# Ensure all static files exist in dashboard/static/
```

---

## 📞 Quick Reference Commands

```bash
# Activate environment
.\.venv\Scripts\Activate.ps1

# Start dashboard
python dashboard/app.py

# Run pipeline
python main_verification_pipeline.py --real-data data/raw/adult.csv --generate

# Train models
python train_all_models.py

# Run tests
pytest tests/ -v

# Check git status
git status

# View logs
cat logs/audit.log
```

---

## 📚 Additional Resources

- [API Documentation](docs/api_documentation.md)
- [Blockchain Setup Guide](docs/blockchain_documentation.md)
- [Project Methodology](docs/Project_Methodology.txt)
- [UML Diagrams](docs/UML_Diagrams.txt)

---

## 👤 Author

**Ashish Pandey**  
Final Year Project - Blockchain-Based Synthetic Data Verification System

---

*Last Updated: December 18, 2025*
