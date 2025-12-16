"""
Dashboard Application
Flask-based web dashboard for synthetic data verification.
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import io
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_system.privacy_verifier import PrivacyVerifier, verify_privacy
from audit_system.utility_verifier import UtilityVerifier, verify_utility
from audit_system.bias_detector import BiasDetector, detect_bias
from audit_system.consensus_engine import ConsensusEngine
from blockchain.api.blockchain_client import BlockchainClient, compute_data_hash
from blockchain.api.verification_orchestrator import VerificationOrchestrator, verify_synthetic_data

app = Flask(__name__)
CORS(app)

# Initialize components
orchestrator = VerificationOrchestrator(min_verifiers=3, approval_threshold=70.0)
blockchain = BlockchainClient()

# Storage for uploaded data
uploaded_data = {}


@app.route('/')
def index():
    """Home page."""
    return render_template('index.html') if os.path.exists('templates/index.html') else jsonify({
        'service': 'Synthetic Data Verification API',
        'version': '1.0.0',
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
    Upload real and synthetic datasets.
    
    Expects JSON with:
    - real_data: List of dictionaries (or CSV file)
    - synthetic_data: List of dictionaries (or CSV file)
    - categorical_columns: List of categorical column names
    - protected_attributes: List of protected attribute columns
    - target_column: Target column name
    """
    try:
        # Handle file uploads
        if 'real_file' in request.files and 'synthetic_file' in request.files:
            real_file = request.files['real_file']
            synthetic_file = request.files['synthetic_file']
            
            real_data = pd.read_csv(real_file)
            synthetic_data = pd.read_csv(synthetic_file)
            
            categorical_columns = request.form.get('categorical_columns', '').split(',')
            categorical_columns = [c.strip() for c in categorical_columns if c.strip()]
            
            protected_attributes = request.form.get('protected_attributes', '').split(',')
            protected_attributes = [p.strip() for p in protected_attributes if p.strip()]
            
            target_column = request.form.get('target_column', None)
            
        # Handle JSON data
        else:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            real_data = pd.DataFrame(data.get('real_data', []))
            synthetic_data = pd.DataFrame(data.get('synthetic_data', []))
            categorical_columns = data.get('categorical_columns', [])
            protected_attributes = data.get('protected_attributes', [])
            target_column = data.get('target_column', None)
        
        if real_data.empty or synthetic_data.empty:
            return jsonify({'error': 'Both real and synthetic data must be provided'}), 400
        
        # Generate upload ID
        upload_id = compute_data_hash(synthetic_data)[:16]
        
        # Store data
        uploaded_data[upload_id] = {
            'real_data': real_data,
            'synthetic_data': synthetic_data,
            'categorical_columns': categorical_columns,
            'protected_attributes': protected_attributes,
            'target_column': target_column,
            'uploaded_at': datetime.now().isoformat()
        }
        
        return jsonify({
            'status': 'success',
            'upload_id': upload_id,
            'real_data_shape': list(real_data.shape),
            'synthetic_data_shape': list(synthetic_data.shape),
            'columns': list(real_data.columns),
            'data_hash': compute_data_hash(synthetic_data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify', methods=['POST'])
def run_verification():
    """
    Run verification on uploaded data.
    
    Expects JSON with:
    - upload_id: ID from upload endpoint
    - num_verifiers: Number of verifiers for consensus (default: 3)
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
        result = orchestrator.run_distributed_verification(request_id, num_verifiers)
        
        return jsonify({
            'status': 'success',
            'request_id': request_id,
            'verification_result': result
        })
        
    except Exception as e:
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
    """Download compliance report as JSON file."""
    try:
        regulation = request.args.get('regulation', 'GDPR')
        report = orchestrator.generate_compliance_report(request_id, regulation)
        
        # Create temporary file
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


@app.route('/api/blockchain/stats')
def blockchain_stats():
    """Get blockchain statistics."""
    try:
        stats = blockchain.get_blockchain_stats()
        consensus_stats = orchestrator.consensus_engine.get_verification_stats()
        
        return jsonify({
            'blockchain': stats,
            'consensus': consensus_stats
        })
    except Exception as e:
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
