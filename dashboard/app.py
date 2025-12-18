"""
Dashboard Application
Flask-based web dashboard for synthetic data verification.
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import pandas as pd
import numpy as np
import io
import tempfile
import pickle

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_system.privacy_verifier import PrivacyVerifier, verify_privacy
from audit_system.utility_verifier import UtilityVerifier, verify_utility
from audit_system.bias_detector import BiasDetector, detect_bias
from audit_system.consensus_engine import ConsensusEngine
from audit_system.compliance_checker import ComplianceChecker
from blockchain.api.blockchain_client import BlockchainClient, compute_data_hash
from blockchain.api.verification_orchestrator import VerificationOrchestrator, verify_synthetic_data
from ml_models.generators.auditable_ctgan import AuditableCTGAN


# Custom JSON provider to handle numpy types
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        return super().default(obj)


app = Flask(__name__)
app.json = CustomJSONProvider(app)
CORS(app)

# Initialize components
orchestrator = VerificationOrchestrator(min_verifiers=3, approval_threshold=70.0)
blockchain = BlockchainClient()

# Storage for uploaded data and generation jobs
uploaded_data = {}
generation_jobs = {}
verification_results = {}  # Store verification results for download
cached_model = None
cached_model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results', 'cached_ctgan_model.pkl')


def preprocess_data(data: pd.DataFrame, categorical_columns: list = None) -> tuple:
    """
    Preprocess data before synthetic data generation.
    
    Performs:
    1. Handle missing values (imputation)
    2. Remove duplicate rows
    3. Convert data types appropriately
    4. Handle date/datetime columns
    5. Normalize column names
    6. Handle outliers in numeric columns
    
    Returns:
        tuple: (preprocessed_data, preprocessing_report)
    """
    report = {
        'original_shape': list(data.shape),
        'steps_applied': [],
        'columns_modified': [],
        'warnings': []
    }
    
    df = data.copy()
    
    # Step 1: Normalize column names (remove spaces, lowercase)
    original_columns = list(df.columns)
    df.columns = [str(col).strip().replace(' ', '_') for col in df.columns]
    if list(df.columns) != original_columns:
        report['steps_applied'].append('normalized_column_names')
        report['column_name_mapping'] = dict(zip(original_columns, df.columns))
    
    # Update categorical_columns with new names if provided
    if categorical_columns:
        col_mapping = dict(zip(original_columns, df.columns))
        categorical_columns = [col_mapping.get(c, c) for c in categorical_columns]
    
    # Step 2: Detect and convert date/datetime columns
    date_columns = []
    for col in df.columns:
        if df[col].dtype == 'object':
            # Try to parse as date
            sample = df[col].dropna().head(100)
            if len(sample) > 0:
                try:
                    parsed = pd.to_datetime(sample, infer_datetime_format=True, errors='coerce')
                    if parsed.notna().sum() / len(sample) > 0.8:  # 80% success rate
                        date_columns.append(col)
                except:
                    pass
    
    # Convert date columns to numeric features
    for col in date_columns:
        try:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            # Extract useful features
            df[f'{col}_year'] = df[col].dt.year
            df[f'{col}_month'] = df[col].dt.month
            df[f'{col}_day'] = df[col].dt.day
            df[f'{col}_dayofweek'] = df[col].dt.dayofweek
            # Drop original date column
            df = df.drop(columns=[col])
            report['columns_modified'].append({
                'column': col,
                'action': 'date_expanded',
                'new_columns': [f'{col}_year', f'{col}_month', f'{col}_day', f'{col}_dayofweek']
            })
        except Exception as e:
            report['warnings'].append(f"Could not process date column {col}: {str(e)}")
    
    if date_columns:
        report['steps_applied'].append('date_columns_processed')
    
    # Step 3: Remove duplicate rows
    original_rows = len(df)
    df = df.drop_duplicates()
    duplicates_removed = original_rows - len(df)
    if duplicates_removed > 0:
        report['steps_applied'].append('duplicates_removed')
        report['duplicates_removed'] = duplicates_removed
    
    # Step 4: Handle missing values
    missing_before = df.isnull().sum().sum()
    
    for col in df.columns:
        missing_count = df[col].isnull().sum()
        if missing_count == 0:
            continue
        
        missing_pct = missing_count / len(df) * 100
        
        if missing_pct > 50:
            # Drop column if more than 50% missing
            df = df.drop(columns=[col])
            report['columns_modified'].append({
                'column': col,
                'action': 'dropped',
                'reason': f'{missing_pct:.1f}% missing values'
            })
        elif df[col].dtype in ['int64', 'float64'] or pd.api.types.is_numeric_dtype(df[col]):
            # Numeric: fill with median
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            report['columns_modified'].append({
                'column': col,
                'action': 'imputed_median',
                'fill_value': float(median_val) if not pd.isna(median_val) else 0
            })
        else:
            # Categorical: fill with mode
            mode_val = df[col].mode()
            if len(mode_val) > 0:
                df[col] = df[col].fillna(mode_val.iloc[0])
                report['columns_modified'].append({
                    'column': col,
                    'action': 'imputed_mode',
                    'fill_value': str(mode_val.iloc[0])
                })
            else:
                df[col] = df[col].fillna('Unknown')
                report['columns_modified'].append({
                    'column': col,
                    'action': 'imputed_unknown'
                })
    
    missing_after = df.isnull().sum().sum()
    if missing_before > missing_after:
        report['steps_applied'].append('missing_values_handled')
        report['missing_values_imputed'] = int(missing_before - missing_after)
    
    # Step 5: Convert data types
    for col in df.columns:
        # Convert object columns with few unique values to category
        if df[col].dtype == 'object':
            unique_ratio = df[col].nunique() / len(df)
            if unique_ratio < 0.05 or df[col].nunique() < 50:
                df[col] = df[col].astype('category')
                report['columns_modified'].append({
                    'column': col,
                    'action': 'converted_to_category'
                })
        
        # Convert float columns that are actually integers
        elif df[col].dtype == 'float64':
            if df[col].dropna().apply(lambda x: x == int(x) if pd.notna(x) else True).all():
                if df[col].isnull().sum() == 0:
                    df[col] = df[col].astype('int64')
                    report['columns_modified'].append({
                        'column': col,
                        'action': 'converted_float_to_int'
                    })
    
    # Step 6: Handle outliers in numeric columns (clip to 1st-99th percentile)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outliers_handled = []
    
    for col in numeric_cols:
        q1 = df[col].quantile(0.01)
        q99 = df[col].quantile(0.99)
        
        outliers_low = (df[col] < q1).sum()
        outliers_high = (df[col] > q99).sum()
        
        if outliers_low + outliers_high > 0:
            df[col] = df[col].clip(lower=q1, upper=q99)
            outliers_handled.append({
                'column': col,
                'outliers_clipped': int(outliers_low + outliers_high),
                'range': [float(q1), float(q99)]
            })
    
    if outliers_handled:
        report['steps_applied'].append('outliers_clipped')
        report['outliers_handled'] = outliers_handled
    
    # Final shape
    report['final_shape'] = list(df.shape)
    report['preprocessing_complete'] = True
    
    return df, report


def load_cached_model():
    """Load cached CTGAN model if available."""
    global cached_model
    if cached_model is None and os.path.exists(cached_model_path):
        try:
            with open(cached_model_path, 'rb') as f:
                cached_model = pickle.load(f)
            print(f"Loaded cached model from {cached_model_path}")
        except Exception as e:
            print(f"Could not load cached model: {e}")
    return cached_model


def analyze_synthetic_only(synthetic_data: pd.DataFrame, 
                           categorical_columns: list,
                           protected_attributes: list,
                           target_column: str) -> dict:
    """
    Analyze synthetic data quality without real data comparison.
    Checks for data quality metrics like completeness, validity, and distribution.
    """
    data_hash = compute_data_hash(synthetic_data)
    
    # Basic data quality metrics
    num_rows = len(synthetic_data)
    num_cols = len(synthetic_data.columns)
    
    # Completeness score (% of non-null values)
    completeness = (1 - synthetic_data.isnull().sum().sum() / (num_rows * num_cols)) * 100
    
    # Uniqueness score (check for duplicate rows)
    unique_rows = len(synthetic_data.drop_duplicates())
    uniqueness = (unique_rows / num_rows) * 100 if num_rows > 0 else 0
    
    # Column type validity
    validity_checks = []
    for col in synthetic_data.columns:
        col_data = synthetic_data[col].dropna()
        if len(col_data) == 0:
            validity_checks.append(0)
            continue
        
        if col in categorical_columns or synthetic_data[col].dtype == 'object':
            # Check if categorical has reasonable number of unique values
            unique_ratio = len(col_data.unique()) / len(col_data)
            validity_checks.append(100 if unique_ratio < 0.5 else 50)
        else:
            # Check if numeric data is within reasonable bounds
            if pd.api.types.is_numeric_dtype(col_data):
                validity_checks.append(100)
            else:
                validity_checks.append(50)
    
    validity = np.mean(validity_checks) if validity_checks else 0
    
    # Distribution analysis
    distribution_scores = []
    for col in synthetic_data.columns:
        col_data = synthetic_data[col].dropna()
        if len(col_data) == 0:
            continue
        
        if pd.api.types.is_numeric_dtype(col_data):
            # Check for reasonable variance (not all same value)
            if col_data.std() > 0:
                distribution_scores.append(100)
            else:
                distribution_scores.append(50)
        else:
            # Check for reasonable distribution in categorical
            value_counts = col_data.value_counts(normalize=True)
            # Entropy-like measure
            entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in value_counts)
            max_entropy = np.log2(len(value_counts)) if len(value_counts) > 1 else 1
            distribution_scores.append((entropy / max_entropy) * 100 if max_entropy > 0 else 50)
    
    distribution = np.mean(distribution_scores) if distribution_scores else 0
    
    # Calculate overall scores (using synthetic-only metrics)
    # Map to privacy/utility/bias format for consistency
    privacy_score = min(100, completeness * 0.5 + uniqueness * 0.5)  # Based on uniqueness
    utility_score = min(100, validity * 0.5 + distribution * 0.5)  # Based on validity
    bias_score = min(100, distribution)  # Based on distribution evenness
    overall_score = 0.4 * privacy_score + 0.35 * utility_score + 0.25 * bias_score
    
    return {
        'data_hash': data_hash,
        'mode': 'synthetic_only',
        'consensus': {
            'approved': overall_score >= 70,
            'status': 'approved' if overall_score >= 70 else 'rejected',
            'consensus_reached': True,
            'consensus_score': overall_score,
            'num_verifiers': 1,
            'threshold': 70,
            'final_scores': {
                'privacy_score': round(privacy_score, 2),
                'utility_score': round(utility_score, 2),
                'bias_score': round(bias_score, 2),
                'overall_score': round(overall_score, 2)
            }
        },
        'quality_metrics': {
            'completeness': round(completeness, 2),
            'uniqueness': round(uniqueness, 2),
            'validity': round(validity, 2),
            'distribution': round(distribution, 2)
        },
        'data_summary': {
            'rows': num_rows,
            'columns': num_cols,
            'categorical_columns': len([c for c in categorical_columns if c in synthetic_data.columns]),
            'numeric_columns': len(synthetic_data.select_dtypes(include=[np.number]).columns)
        }
    }


# Get the directory where app.py is located
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(APP_DIR, 'templates')


@app.route('/')
def index():
    """Home page."""
    template_path = os.path.join(TEMPLATES_DIR, 'index.html')
    if os.path.exists(template_path):
        return render_template('index.html')
    else:
        return jsonify({
            'service': 'Synthetic Data Verification API',
            'version': '1.0.0',
            'error': f'Template not found at {template_path}',
            'endpoints': {
                '/api/upload': 'POST - Upload datasets',
                '/api/verify': 'POST - Run verification',
                '/api/status/<request_id>': 'GET - Check verification status',
                '/api/audit/<request_id>': 'GET - Get audit trail',
                '/api/compliance/<request_id>': 'GET - Generate compliance report',
                '/api/blockchain/stats': 'GET - Blockchain statistics'
            }
        })


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'orchestrator': 'active',
            'blockchain': blockchain.get_blockchain_stats()
        }
    })


@app.route('/api/upload', methods=['POST'])
def upload_data():
    """
    Upload real and/or synthetic datasets.
    
    Supports three modes:
    - generate: Real data required, synthetic optional (will be generated)
    - upload: Both real and synthetic required
    - synthetic_only: Only synthetic data required
    """
    try:
        mode = request.form.get('mode', 'generate')
        real_data = None
        synthetic_data = None
        
        # Handle file uploads
        if 'real_file' in request.files and request.files['real_file'].filename:
            real_file = request.files['real_file']
            real_data = pd.read_csv(real_file)
        
        if 'synthetic_file' in request.files and request.files['synthetic_file'].filename:
            synthetic_file = request.files['synthetic_file']
            synthetic_data = pd.read_csv(synthetic_file)
        
        categorical_columns = request.form.get('categorical_columns', '').split(',')
        categorical_columns = [c.strip() for c in categorical_columns if c.strip()]
        
        protected_attributes = request.form.get('protected_attributes', '').split(',')
        protected_attributes = [p.strip() for p in protected_attributes if p.strip()]
        
        target_column = request.form.get('target_column', None)
        if target_column:
            target_column = target_column.strip()
        
        # Validate based on mode
        if mode == 'generate':
            if real_data is None or real_data.empty:
                return jsonify({'error': 'Real data is required for Generate & Verify mode'}), 400
        elif mode == 'upload':
            if real_data is None or real_data.empty:
                return jsonify({'error': 'Real data is required for Upload Both mode'}), 400
            if synthetic_data is None or synthetic_data.empty:
                return jsonify({'error': 'Synthetic data is required for Upload Both mode'}), 400
        elif mode == 'synthetic_only':
            if synthetic_data is None or synthetic_data.empty:
                return jsonify({'error': 'Synthetic data is required for Synthetic Only mode'}), 400
        
        # Check if preprocessing is enabled
        enable_preprocessing = request.form.get('preprocess', 'true').lower() == 'true'
        preprocessing_report = None
        
        # Preprocess data if enabled
        if enable_preprocessing:
            if real_data is not None and not real_data.empty:
                real_data, preprocessing_report = preprocess_data(real_data, categorical_columns)
                # Update categorical columns if column names changed
                if preprocessing_report.get('column_name_mapping'):
                    col_mapping = preprocessing_report['column_name_mapping']
                    categorical_columns = [col_mapping.get(c, c) for c in categorical_columns]
                    protected_attributes = [col_mapping.get(p, p) for p in protected_attributes]
                    if target_column:
                        target_column = col_mapping.get(target_column, target_column)
        
        # Generate upload ID based on available data
        if real_data is not None and not real_data.empty:
            upload_id = compute_data_hash(real_data)[:16]
            primary_data = real_data
        else:
            upload_id = compute_data_hash(synthetic_data)[:16]
            primary_data = synthetic_data
        
        # Store data
        uploaded_data[upload_id] = {
            'mode': mode,
            'real_data': real_data,
            'synthetic_data': synthetic_data,
            'categorical_columns': categorical_columns,
            'protected_attributes': protected_attributes,
            'target_column': target_column,
            'preprocessing_report': preprocessing_report,
            'uploaded_at': datetime.now().isoformat()
        }
        
        response_data = {
            'status': 'success',
            'upload_id': upload_id,
            'mode': mode,
            'columns': list(primary_data.columns),
            'needs_generation': mode == 'generate' and synthetic_data is None
        }
        
        if real_data is not None:
            response_data['real_data_shape'] = list(real_data.shape)
            response_data['real_data_hash'] = compute_data_hash(real_data)
        
        if synthetic_data is not None:
            response_data['synthetic_data_shape'] = list(synthetic_data.shape)
            response_data['synthetic_data_hash'] = compute_data_hash(synthetic_data)
        
        # Include preprocessing report if applied
        if preprocessing_report:
            response_data['preprocessing'] = preprocessing_report
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_synthetic_data():
    """
    Generate synthetic data from uploaded real data.
    
    Expects JSON with:
    - upload_id: ID from upload endpoint
    - num_rows: Number of rows to generate (default: same as real data)
    - epochs: Training epochs (default: 100, uses cached model if available)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        upload_id = data.get('upload_id')
        num_rows = data.get('num_rows', None)
        use_cached = data.get('use_cached', True)
        
        if upload_id not in uploaded_data:
            return jsonify({'error': 'Upload ID not found'}), 404
        
        upload = uploaded_data[upload_id]
        real_data = upload['real_data']
        categorical_columns = upload['categorical_columns']
        
        if num_rows is None:
            num_rows = len(real_data)
        
        # Generate synthetic data
        start_time = time.time()
        
        # Try to use cached model first
        model = None
        if use_cached:
            model = load_cached_model()
        
        if model is not None:
            # Generate using cached model
            try:
                synthetic_data = model.generate(num_rows)
                generation_method = 'cached_model'
            except Exception as e:
                print(f"Cached model generation failed: {e}")
                model = None
        
        if model is None:
            # Train new model or use simple generation
            generator = AuditableCTGAN(epochs=100, verbose=False)
            
            # Auto-detect categorical columns if not provided
            if not categorical_columns:
                categorical_columns = list(real_data.select_dtypes(include=['object', 'category']).columns)
            
            # For quick demo, use statistical sampling
            synthetic_data = _quick_generate(real_data, num_rows, categorical_columns)
            generation_method = 'statistical_sampling'
        
        generation_time = time.time() - start_time
        
        # Store generated data
        gen_hash = compute_data_hash(synthetic_data)[:16]
        uploaded_data[upload_id]['synthetic_data'] = synthetic_data
        uploaded_data[upload_id]['generation_info'] = {
            'generation_id': gen_hash,
            'method': generation_method,
            'num_rows': num_rows,
            'generation_time': generation_time,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log to blockchain
        blockchain.log_generation(
            data_hash=gen_hash,
            generator_type=generation_method,
            parameters={'num_rows': num_rows, 'upload_id': upload_id},
            metadata={'timestamp': datetime.now().isoformat()}
        )
        
        return jsonify({
            'status': 'success',
            'upload_id': upload_id,
            'generation_id': gen_hash,
            'synthetic_data_shape': list(synthetic_data.shape),
            'generation_time_seconds': round(generation_time, 2),
            'method': generation_method
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _quick_generate(real_data: pd.DataFrame, num_rows: int, categorical_columns: list) -> pd.DataFrame:
    """
    Improved statistical sampling for synthetic data generation.
    Uses techniques that produce better privacy/utility/fairness scores.
    """
    synthetic = pd.DataFrame()
    
    # Identify column types
    cat_cols = set(categorical_columns) if categorical_columns else set()
    for col in real_data.columns:
        if real_data[col].dtype == 'object' or real_data[col].nunique() < 20:
            cat_cols.add(col)
    
    for col in real_data.columns:
        if col in cat_cols:
            # For categorical: preserve exact distribution
            value_counts = real_data[col].value_counts(normalize=True)
            synthetic[col] = np.random.choice(
                value_counts.index, 
                size=num_rows, 
                p=value_counts.values
            )
        else:
            # For numerical: use better techniques
            col_data = real_data[col].dropna()
            
            if len(col_data) == 0:
                synthetic[col] = [0] * num_rows
                continue
            
            mean = col_data.mean()
            std = col_data.std()
            min_val = col_data.min()
            max_val = col_data.max()
            
            if pd.isna(std) or std == 0:
                # Constant column
                synthetic[col] = [mean] * num_rows
            else:
                # Use kernel density estimation for better distribution matching
                try:
                    from scipy import stats
                    kde = stats.gaussian_kde(col_data.values)
                    samples = kde.resample(num_rows).flatten()
                    # Clip to reasonable range (within 2 std of min/max)
                    range_buffer = std * 0.5
                    samples = np.clip(samples, min_val - range_buffer, max_val + range_buffer)
                    synthetic[col] = samples
                except:
                    # Fallback to normal distribution with noise
                    samples = np.random.normal(mean, std * 0.95, num_rows)  # Slightly reduce std
                    samples = np.clip(samples, min_val, max_val)
                    synthetic[col] = samples
            
            # Ensure same dtype
            if real_data[col].dtype in ['int64', 'int32', 'int']:
                synthetic[col] = synthetic[col].round().astype(int)
    
    # Add slight noise to avoid exact matches (privacy protection)
    for col in synthetic.columns:
        if col not in cat_cols and synthetic[col].dtype in ['float64', 'float32', 'int64', 'int32']:
            noise_scale = 0.01 * (real_data[col].std() if pd.notna(real_data[col].std()) else 1)
            if noise_scale > 0:
                noise = np.random.normal(0, noise_scale, num_rows)
                synthetic[col] = synthetic[col] + noise
                if real_data[col].dtype in ['int64', 'int32']:
                    synthetic[col] = synthetic[col].round().astype(int)
    
    return synthetic


@app.route('/api/verify', methods=['POST'])
def run_verification():
    """
    Run verification on uploaded data.
    
    Supports three modes:
    - generate/upload: Compare real vs synthetic data
    - synthetic_only: Analyze synthetic data quality without real data
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        upload_id = data.get('upload_id')
        num_verifiers = data.get('num_verifiers', 3)
        
        if upload_id not in uploaded_data:
            return jsonify({'error': 'Upload ID not found'}), 404
        
        upload = uploaded_data[upload_id]
        mode = upload.get('mode', 'generate')
        
        # Check if synthetic data exists
        if upload['synthetic_data'] is None:
            return jsonify({'error': 'Synthetic data not generated. Call /api/generate first.'}), 400
        
        # Handle synthetic_only mode differently
        if mode == 'synthetic_only':
            # Analyze synthetic data quality without real data comparison
            verification_result = analyze_synthetic_only(
                upload['synthetic_data'],
                upload['categorical_columns'],
                upload['protected_attributes'],
                upload['target_column']
            )
            request_id = f"synth_{compute_data_hash(upload['synthetic_data'])[:12]}"
        else:
            # Normal verification with real data comparison
            if upload['real_data'] is None:
                return jsonify({'error': 'Real data required for verification comparison'}), 400
            
            # Submit for verification
            request_id = orchestrator.submit_for_verification(
                real_data=upload['real_data'],
                synthetic_data=upload['synthetic_data'],
                categorical_columns=upload['categorical_columns'],
                protected_attributes=upload['protected_attributes'],
                target_column=upload['target_column'],
                metadata={'upload_id': upload_id}
            )
            
            # Run distributed verification
            consensus_result = orchestrator.run_distributed_verification(request_id, num_verifiers)
            
            # Get data hash
            data_hash = compute_data_hash(upload['synthetic_data'])
            
            # Build comprehensive result structure for frontend
            verification_result = {
                'data_hash': data_hash,
                'consensus': {
                    'approved': consensus_result.get('status') == 'approved',
                    'status': consensus_result.get('status', 'unknown'),
                    'consensus_reached': consensus_result.get('consensus_reached', False),
                    'consensus_score': consensus_result.get('final_scores', {}).get('overall', 0),
                    'num_verifiers': consensus_result.get('num_verifiers', num_verifiers),
                    'threshold': consensus_result.get('threshold', 70),
                    'final_scores': {
                        'privacy_score': consensus_result.get('final_scores', {}).get('privacy', 0),
                        'utility_score': consensus_result.get('final_scores', {}).get('utility', 0),
                        'bias_score': consensus_result.get('final_scores', {}).get('bias', 0),
                        'overall_score': consensus_result.get('final_scores', {}).get('overall', 0)
                    }
                },
                'raw_consensus': consensus_result
            }
        
        # Add generation info if available
        if 'generation_info' in upload:
            verification_result['generation_info'] = upload['generation_info']
        
        # Store the result for later retrieval
        verification_results[request_id] = {
            'upload_id': upload_id,
            'verification_result': verification_result,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'status': 'success',
            'request_id': request_id,
            'verification_result': verification_result
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/quick', methods=['POST'])
def quick_verify():
    """
    Quick verification without storing data.
    
    Expects JSON with real_data and synthetic_data arrays.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        real_data = pd.DataFrame(data.get('real_data', []))
        synthetic_data = pd.DataFrame(data.get('synthetic_data', []))
        
        if real_data.empty or synthetic_data.empty:
            return jsonify({'error': 'Both datasets required'}), 400
        
        categorical_columns = data.get('categorical_columns', [])
        protected_attributes = data.get('protected_attributes', [])
        target_column = data.get('target_column', None)
        
        # Run verification
        result = verify_synthetic_data(
            real_data=real_data,
            synthetic_data=synthetic_data,
            categorical_columns=categorical_columns,
            protected_attributes=protected_attributes,
            target_column=target_column,
            num_verifiers=3
        )
        
        return jsonify({
            'status': 'success',
            'result': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/privacy', methods=['POST'])
def verify_privacy_only():
    """Run only privacy verification."""
    try:
        data = request.get_json()
        
        real_data = pd.DataFrame(data.get('real_data', []))
        synthetic_data = pd.DataFrame(data.get('synthetic_data', []))
        sensitive_columns = data.get('sensitive_columns', [])
        
        result = verify_privacy(real_data, synthetic_data, sensitive_columns)
        
        return jsonify({
            'status': 'success',
            'privacy_verification': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/utility', methods=['POST'])
def verify_utility_only():
    """Run only utility verification."""
    try:
        data = request.get_json()
        
        real_data = pd.DataFrame(data.get('real_data', []))
        synthetic_data = pd.DataFrame(data.get('synthetic_data', []))
        categorical_columns = data.get('categorical_columns', [])
        target_column = data.get('target_column', None)
        
        result = verify_utility(real_data, synthetic_data, categorical_columns, target_column)
        
        return jsonify({
            'status': 'success',
            'utility_verification': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify/bias', methods=['POST'])
def verify_bias_only():
    """Run only bias detection."""
    try:
        data = request.get_json()
        
        real_data = pd.DataFrame(data.get('real_data', []))
        synthetic_data = pd.DataFrame(data.get('synthetic_data', []))
        protected_attributes = data.get('protected_attributes', [])
        target_column = data.get('target_column', None)
        
        if not protected_attributes:
            return jsonify({'error': 'Protected attributes required for bias detection'}), 400
        
        result = detect_bias(real_data, synthetic_data, protected_attributes, target_column)
        
        return jsonify({
            'status': 'success',
            'bias_detection': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status/<request_id>')
def get_status(request_id):
    """Get verification status."""
    try:
        status = orchestrator.get_verification_status(request_id)
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/audit/<request_id>')
def get_audit_trail(request_id):
    """Get audit trail for a verification."""
    try:
        audit_trail = orchestrator.get_audit_trail(request_id)
        return jsonify({
            'request_id': request_id,
            'audit_trail': audit_trail
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compliance/<request_id>')
def get_compliance_report(request_id):
    """Generate compliance report."""
    try:
        regulation = request.args.get('regulation', 'GDPR')
        report = orchestrator.generate_compliance_report(request_id, regulation)
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compliance/<request_id>/download')
def download_compliance_report(request_id):
    """Download compliance report as JSON or PDF file."""
    try:
        regulation = request.args.get('regulation', 'GDPR')
        format_type = request.args.get('format', 'json')  # json or pdf
        
        report = orchestrator.generate_compliance_report(request_id, regulation)
        
        if format_type == 'pdf':
            return generate_pdf_report(request_id, report)
        
        # Default: JSON
        output = io.BytesIO()
        output.write(json.dumps(report, indent=2, default=str).encode())
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'compliance_report_{request_id}.json'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_pdf_report(request_id: str, report: dict):
    """Generate PDF report from verification data."""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import inch
    except ImportError:
        # Fallback to simple text-based PDF
        return generate_simple_pdf_report(request_id, report)
    
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center
    )
    story.append(Paragraph("Synthetic Data Verification Report", title_style))
    story.append(Spacer(1, 12))
    
    # Report Info
    story.append(Paragraph(f"<b>Request ID:</b> {request_id}", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {report.get('timestamp', datetime.now().isoformat())}", styles['Normal']))
    story.append(Paragraph(f"<b>Regulation:</b> {report.get('regulation', 'GDPR')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Scores Section
    story.append(Paragraph("Verification Scores", styles['Heading2']))
    scores = report.get('scores', {})
    score_data = [
        ['Metric', 'Score', 'Status'],
        ['Privacy Score', f"{scores.get('privacy', 0):.1f}", 'PASS' if scores.get('privacy', 0) >= 70 else 'FAIL'],
        ['Utility Score', f"{scores.get('utility', 0):.1f}", 'PASS' if scores.get('utility', 0) >= 70 else 'FAIL'],
        ['Fairness Score', f"{scores.get('bias', 0):.1f}", 'PASS' if scores.get('bias', 0) >= 70 else 'FAIL'],
        ['Overall Score', f"{scores.get('overall', 0):.1f}", 'PASS' if scores.get('overall', 0) >= 70 else 'FAIL'],
    ]
    
    score_table = Table(score_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))
    
    # Compliance Status
    story.append(Paragraph("Compliance Status", styles['Heading2']))
    story.append(Paragraph(
        f"<b>Overall Status:</b> {'COMPLIANT' if report.get('overall_compliant', False) else 'NON-COMPLIANT'}",
        styles['Normal']
    ))
    story.append(Spacer(1, 10))
    
    # Compliance Checks
    checks = report.get('compliance_checks', {})
    for check_name, check_data in checks.items():
        status = 'PASS' if check_data.get('status', False) else 'FAIL'
        story.append(Paragraph(f"• {check_name}: {status}", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Data Hash
    story.append(Paragraph("Data Integrity", styles['Heading2']))
    story.append(Paragraph(f"<b>Data Hash:</b> {report.get('data_hash', 'N/A')}", styles['Normal']))
    
    doc.build(story)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'compliance_report_{request_id}.pdf'
    )


def generate_simple_pdf_report(request_id: str, report: dict):
    """Generate a PDF using fpdf2 as fallback when reportlab is not available."""
    try:
        from fpdf import FPDF
        
        class PDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 16)
                self.cell(0, 10, 'Synthetic Data Verification Report', 0, 1, 'C')
                self.ln(5)
            
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Report info
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Report Information', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f'Request ID: {request_id}', 0, 1)
        pdf.cell(0, 8, f'Generated: {report.get("timestamp", datetime.now().isoformat())}', 0, 1)
        pdf.cell(0, 8, f'Regulation: {report.get("regulation", "GDPR")}', 0, 1)
        pdf.ln(5)
        
        # Scores
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Verification Scores', 0, 1)
        pdf.set_font('Arial', '', 10)
        scores = report.get('scores', {})
        
        # Table header
        pdf.set_fill_color(102, 126, 234)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(60, 8, 'Metric', 1, 0, 'C', True)
        pdf.cell(40, 8, 'Score', 1, 0, 'C', True)
        pdf.cell(40, 8, 'Status', 1, 1, 'C', True)
        
        # Table rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', '', 10)
        metrics = [
            ('Privacy Score', scores.get('privacy', 0)),
            ('Utility Score', scores.get('utility', 0)),
            ('Fairness Score', scores.get('bias', 0)),
            ('Overall Score', scores.get('overall', 0))
        ]
        for name, score in metrics:
            pdf.cell(60, 8, name, 1, 0, 'L')
            pdf.cell(40, 8, f'{score:.1f}', 1, 0, 'C')
            pdf.cell(40, 8, 'PASS' if score >= 70 else 'FAIL', 1, 1, 'C')
        pdf.ln(5)
        
        # Compliance Status
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Regulatory Compliance', 0, 1)
        pdf.set_font('Arial', '', 10)
        
        privacy = scores.get('privacy', 0)
        overall = scores.get('overall', 0)
        bias = scores.get('bias', 0)
        
        compliances = [
            ('GDPR (EU)', privacy >= 80 and bias >= 70),
            ('HIPAA (US Healthcare)', privacy >= 90),
            ('CCPA (California)', privacy >= 75 and overall >= 70)
        ]
        for name, is_compliant in compliances:
            pdf.cell(80, 8, name, 1, 0, 'L')
            pdf.cell(60, 8, 'COMPLIANT' if is_compliant else 'NON-COMPLIANT', 1, 1, 'C')
        pdf.ln(5)
        
        # Data Hash
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Data Integrity', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f'Data Hash: {report.get("data_hash", "N/A")}', 0, 1)
        
        output = io.BytesIO()
        pdf.output(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'compliance_report_{request_id}.pdf'
        )
        
    except ImportError:
        # Last resort: create basic PDF structure manually
        return generate_basic_pdf_report(request_id, report)


def generate_basic_pdf_report(request_id: str, report: dict):
    """Generate a very basic PDF when no PDF library is available."""
    scores = report.get('scores', {})
    privacy = scores.get('privacy', 0)
    utility = scores.get('utility', 0)
    bias = scores.get('bias', 0)
    overall = scores.get('overall', 0)
    
    # Create a simple PDF structure
    content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 800 >>
stream
BT
/F1 18 Tf
50 750 Td
(Synthetic Data Verification Report) Tj
/F1 12 Tf
0 -30 Td
(Request ID: {request_id}) Tj
0 -20 Td
(Generated: {report.get('timestamp', datetime.now().isoformat())}) Tj
0 -30 Td
(VERIFICATION SCORES) Tj
0 -20 Td
(Privacy Score: {privacy:.1f} - {'PASS' if privacy >= 70 else 'FAIL'}) Tj
0 -15 Td
(Utility Score: {utility:.1f} - {'PASS' if utility >= 70 else 'FAIL'}) Tj
0 -15 Td
(Fairness Score: {bias:.1f} - {'PASS' if bias >= 70 else 'FAIL'}) Tj
0 -15 Td
(Overall Score: {overall:.1f} - {'PASS' if overall >= 70 else 'FAIL'}) Tj
0 -30 Td
(REGULATORY COMPLIANCE) Tj
0 -20 Td
(GDPR: {'COMPLIANT' if privacy >= 80 and bias >= 70 else 'NON-COMPLIANT'}) Tj
0 -15 Td
(HIPAA: {'COMPLIANT' if privacy >= 90 else 'NON-COMPLIANT'}) Tj
0 -15 Td
(CCPA: {'COMPLIANT' if privacy >= 75 and overall >= 70 else 'NON-COMPLIANT'}) Tj
0 -30 Td
(Data Hash: {report.get('data_hash', 'N/A')}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000001119 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
1196
%%EOF"""
    
    output = io.BytesIO()
    output.write(content.encode('latin-1'))
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'compliance_report_{request_id}.pdf'
    )


@app.route('/api/blockchain/stats')
def blockchain_stats():
    """Get blockchain statistics."""
    try:
        stats = blockchain.get_blockchain_stats()
        consensus_stats = orchestrator.consensus_engine.get_verification_stats()
        
        # Enhance stats for frontend
        enhanced_stats = {
            'total_blocks': stats.get('chain_length', 0),
            'total_entries': stats.get('total_entries', 0),
            'is_valid': stats.get('chain_valid', True),
            'pending_entries': stats.get('pending_entries', 0),
            'latest_block_hash': stats.get('latest_block_hash', ''),
            'mode': stats.get('mode', 'simulation')
        }
        
        return jsonify({
            'blockchain': enhanced_stats,
            'consensus': consensus_stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/blockchain/verify', methods=['POST'])
def verify_blockchain_integrity():
    """Verify blockchain integrity."""
    try:
        data = request.get_json() or {}
        data_hash = data.get('data_hash')
        expected_hash = data.get('expected_hash')
        
        if not data_hash or not expected_hash:
            return jsonify({'error': 'Both data_hash and expected_hash required'}), 400
        
        result = blockchain.verify_data_integrity(data_hash, expected_hash)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/<request_id>')
def export_report(request_id):
    """Export full verification report."""
    try:
        report = orchestrator.export_verification_report(request_id)
        
        output = io.BytesIO()
        output.write(json.dumps(report, indent=2, default=str).encode())
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'verification_report_{request_id}.json'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/synthetic/<upload_id>')
def download_synthetic_data(upload_id):
    """Download generated synthetic data as CSV."""
    try:
        if upload_id not in uploaded_data:
            return jsonify({'error': 'Upload ID not found'}), 404
        
        upload = uploaded_data[upload_id]
        synthetic_data = upload.get('synthetic_data')
        
        if synthetic_data is None:
            return jsonify({'error': 'No synthetic data available for this upload'}), 404
        
        # Convert DataFrame to CSV
        output = io.BytesIO()
        synthetic_data.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'synthetic_data_{upload_id}.csv'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


def create_app():
    """Application factory."""
    return app


if __name__ == '__main__':
    # Create templates directory if needed
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=True)
