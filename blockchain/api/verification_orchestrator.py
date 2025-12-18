"""
Verification Orchestrator Module
Coordinates distributed verification across multiple peers.
"""

import hashlib
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from audit_system.privacy_verifier import PrivacyVerifier
from audit_system.utility_verifier import UtilityVerifier
from audit_system.bias_detector import BiasDetector
from audit_system.consensus_engine import ConsensusEngine, VerificationStatus
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode, compute_data_hash


@dataclass
class VerificationRequest:
    """Represents a verification request."""
    request_id: str
    data_hash: str
    real_data_path: Optional[str]
    synthetic_data_path: Optional[str]
    categorical_columns: List[str]
    protected_attributes: List[str]
    target_column: Optional[str]
    created_at: str
    status: str
    
    def to_dict(self) -> Dict:
        return {
            'request_id': self.request_id,
            'data_hash': self.data_hash,
            'real_data_path': self.real_data_path,
            'synthetic_data_path': self.synthetic_data_path,
            'categorical_columns': self.categorical_columns,
            'protected_attributes': self.protected_attributes,
            'target_column': self.target_column,
            'created_at': self.created_at,
            'status': self.status
        }


class VerificationOrchestrator:
    """
    Orchestrates the complete verification workflow:
    1. Data submission and hashing
    2. Privacy verification
    3. Utility verification
    4. Bias detection
    5. Consensus gathering
    6. Blockchain logging
    """
    
    def __init__(self, min_verifiers: int = 3, 
                 approval_threshold: float = 70.0,
                 blockchain_mode: BlockchainMode = BlockchainMode.SIMULATION):
        """
        Initialize the orchestrator.
        
        Args:
            min_verifiers: Minimum verifiers for consensus
            approval_threshold: Score threshold for approval
            blockchain_mode: Blockchain backend mode (BlockchainMode enum)
        """
        self.consensus_engine = ConsensusEngine(
            min_verifiers=min_verifiers,
            approval_threshold=approval_threshold
        )
        self.blockchain = BlockchainClient(mode=blockchain_mode)
        
        # Request tracking
        self.requests: Dict[str, VerificationRequest] = {}
        self.results: Dict[str, Dict] = {}
        
        # Verifier callbacks
        self.verifier_callbacks: Dict[str, Callable] = {}
        
        self._lock = threading.Lock()
    
    def submit_for_verification(self, real_data, synthetic_data,
                                categorical_columns: Optional[List[str]] = None,
                                protected_attributes: Optional[List[str]] = None,
                                target_column: Optional[str] = None,
                                metadata: Optional[Dict] = None) -> str:
        """
        Submit data for verification.
        
        Args:
            real_data: Original dataset (DataFrame)
            synthetic_data: Synthetic dataset (DataFrame)
            categorical_columns: List of categorical columns
            protected_attributes: List of protected attribute columns
            target_column: Target column for ML tests
            metadata: Additional metadata
            
        Returns:
            Request ID
        """
        import pandas as pd
        
        # Compute data hash
        data_hash = compute_data_hash(synthetic_data)
        
        # Generate request ID
        request_id = hashlib.sha256(
            f"{data_hash}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Store data for verification
        self.results[request_id] = {
            'real_data': real_data,
            'synthetic_data': synthetic_data,
            'categorical_columns': categorical_columns or [],
            'protected_attributes': protected_attributes or [],
            'target_column': target_column,
            'metadata': metadata or {}
        }
        
        # Create request record
        request = VerificationRequest(
            request_id=request_id,
            data_hash=data_hash,
            real_data_path=None,
            synthetic_data_path=None,
            categorical_columns=categorical_columns or [],
            protected_attributes=protected_attributes or [],
            target_column=target_column,
            created_at=datetime.now().isoformat(),
            status='submitted'
        )
        
        with self._lock:
            self.requests[request_id] = request
        
        # Create consensus verification request
        self.consensus_engine.create_verification_request(data_hash, metadata)
        
        # Log to blockchain
        self.blockchain.log_generation(
            data_hash=data_hash,
            generator_type=metadata.get('generator_type', 'unknown') if metadata else 'unknown',
            parameters=metadata.get('parameters', {}) if metadata else {},
            metadata={'request_id': request_id}
        )
        
        return request_id
    
    def run_verification(self, request_id: str, 
                        verifier_id: str) -> Dict:
        """
        Run complete verification as a verifier.
        
        Args:
            request_id: Verification request ID
            verifier_id: Unique verifier identifier
            
        Returns:
            Verification results
        """
        if request_id not in self.results:
            return {'error': 'Request not found'}
        
        data = self.results[request_id]
        real_data = data['real_data']
        synthetic_data = data['synthetic_data']
        categorical_columns = data['categorical_columns']
        protected_attributes = data['protected_attributes']
        target_column = data['target_column']
        
        results = {}
        
        # 1. Privacy Verification
        try:
            privacy_verifier = PrivacyVerifier(
                real_data, synthetic_data,
                sensitive_columns=protected_attributes
            )
            privacy_results = privacy_verifier.verify_all()
            results['privacy'] = privacy_results
            privacy_score = privacy_results['overall']['privacy_score']
        except Exception as e:
            results['privacy'] = {'error': str(e)}
            privacy_score = 0
        
        # 2. Utility Verification
        try:
            utility_verifier = UtilityVerifier(
                real_data, synthetic_data,
                categorical_columns=categorical_columns,
                target_column=target_column
            )
            utility_results = utility_verifier.verify_all(target_column)
            results['utility'] = utility_results
            utility_score = utility_results['overall']['utility_score']
        except Exception as e:
            results['utility'] = {'error': str(e)}
            utility_score = 0
        
        # 3. Bias Detection
        try:
            if protected_attributes:
                bias_detector = BiasDetector(
                    real_data, synthetic_data,
                    protected_attributes=protected_attributes,
                    target_column=target_column
                )
                bias_results = bias_detector.verify_all()
                results['bias'] = bias_results
                bias_score = bias_results['overall']['fairness_score']
            else:
                results['bias'] = {'skipped': 'No protected attributes specified'}
                bias_score = 100  # Default to pass if not checked
        except Exception as e:
            results['bias'] = {'error': str(e)}
            bias_score = 0
        
        # Submit to consensus engine
        data_hash = compute_data_hash(synthetic_data)
        
        # Find verification_id
        verification_id = None
        for vid, pending in self.consensus_engine.pending_verifications.items():
            if pending['data_hash'] == data_hash:
                verification_id = vid
                break
        
        if verification_id:
            consensus_result = self.consensus_engine.submit_verification(
                verification_id=verification_id,
                verifier_id=verifier_id,
                privacy_score=privacy_score,
                utility_score=utility_score,
                bias_score=bias_score,
                details=results
            )
            results['consensus'] = consensus_result
            
            # Log to blockchain
            self.blockchain.log_verification(
                data_hash=data_hash,
                verification_id=verification_id,
                verifier_id=verifier_id,
                results={
                    'privacy_score': privacy_score,
                    'utility_score': utility_score,
                    'bias_score': bias_score
                }
            )
            
            # If consensus reached, log it
            if consensus_result.get('consensus_reached'):
                self.blockchain.log_consensus(
                    data_hash=data_hash,
                    verification_id=verification_id,
                    consensus_result=consensus_result
                )
                
                # Update request status
                with self._lock:
                    if request_id in self.requests:
                        self.requests[request_id].status = consensus_result['status']
        
        results['summary'] = {
            'privacy_score': privacy_score,
            'utility_score': utility_score,
            'bias_score': bias_score,
            'overall_score': 0.4 * privacy_score + 0.35 * utility_score + 0.25 * bias_score,
            'verifier_id': verifier_id,
            'timestamp': datetime.now().isoformat()
        }
        
        return results
    
    def run_distributed_verification(self, request_id: str,
                                      num_verifiers: int = 3) -> Dict:
        """
        Run verification with multiple simulated verifiers.
        
        Args:
            request_id: Verification request ID
            num_verifiers: Number of verifiers to simulate
            
        Returns:
            Final consensus result
        """
        results = []
        
        for i in range(num_verifiers):
            verifier_id = f"verifier_{i}"
            result = self.run_verification(request_id, verifier_id)
            results.append(result)
        
        # Get final consensus
        if results and 'consensus' in results[-1]:
            return results[-1]['consensus']
        
        return {'error': 'Verification failed', 'individual_results': results}
    
    def get_verification_status(self, request_id: str) -> Dict:
        """Get the current status of a verification request."""
        if request_id not in self.requests:
            return {'error': 'Request not found'}
        
        request = self.requests[request_id]
        
        # Check consensus status
        consensus_status = self.consensus_engine.query_by_data_hash(request.data_hash)
        
        return {
            'request': request.to_dict(),
            'consensus_records': consensus_status
        }
    
    def get_audit_trail(self, request_id: str) -> Dict:
        """Get the complete audit trail for a request."""
        if request_id not in self.requests:
            return {'error': 'Request not found'}
        
        request = self.requests[request_id]
        
        return self.blockchain.get_audit_trail(request.data_hash)
    
    def generate_compliance_report(self, request_id: str,
                                   regulation: str = "GDPR") -> Dict:
        """
        Generate a compliance report for a verification.
        
        Args:
            request_id: Verification request ID
            regulation: Regulation to check against
            
        Returns:
            Compliance report
        """
        if request_id not in self.requests:
            return {'error': 'Request not found'}
        
        request = self.requests[request_id]
        
        # Get consensus result
        consensus_records = self.consensus_engine.query_by_data_hash(request.data_hash)
        
        if not consensus_records:
            return {'error': 'No consensus reached yet'}
        
        latest_consensus = consensus_records[-1]
        
        # GDPR compliance checks
        compliance_checks = {}
        
        if regulation == "GDPR":
            # Article 5 - Data minimization
            compliance_checks['data_minimization'] = {
                'status': latest_consensus['final_privacy_score'] >= 70,
                'score': latest_consensus['final_privacy_score'],
                'article': 'Article 5(1)(c)'
            }
            
            # Article 25 - Data protection by design
            compliance_checks['privacy_by_design'] = {
                'status': latest_consensus['final_privacy_score'] >= 80,
                'score': latest_consensus['final_privacy_score'],
                'article': 'Article 25'
            }
            
            # Article 35 - Data protection impact assessment
            compliance_checks['dpia_ready'] = {
                'status': all([
                    latest_consensus['final_privacy_score'] >= 70,
                    latest_consensus['final_bias_score'] >= 70
                ]),
                'article': 'Article 35'
            }
        
        elif regulation == "HIPAA":
            # Safe Harbor requirements
            compliance_checks['safe_harbor'] = {
                'status': latest_consensus['final_privacy_score'] >= 90,
                'score': latest_consensus['final_privacy_score'],
                'requirement': '45 CFR 164.514(b)'
            }
        
        report = {
            'request_id': request_id,
            'data_hash': request.data_hash,
            'regulation': regulation,
            'timestamp': datetime.now().isoformat(),
            'consensus_status': latest_consensus['status'],
            'scores': {
                'privacy': latest_consensus['final_privacy_score'],
                'utility': latest_consensus['final_utility_score'],
                'bias': latest_consensus['final_bias_score'],
                'overall': latest_consensus['final_overall_score']
            },
            'compliance_checks': compliance_checks,
            'overall_compliant': all(
                check.get('status', False) 
                for check in compliance_checks.values()
            ),
            'audit_trail': self.blockchain.get_audit_trail(request.data_hash)
        }
        
        # Log compliance check to blockchain
        self.blockchain.log_compliance_check(
            data_hash=request.data_hash,
            regulation=regulation,
            compliance_result=report
        )
        
        return report
    
    def export_verification_report(self, request_id: str,
                                    filepath: Optional[str] = None) -> Dict:
        """Export a complete verification report."""
        if request_id not in self.requests:
            return {'error': 'Request not found'}
        
        request = self.requests[request_id]
        
        report = {
            'report_type': 'Synthetic Data Verification Report',
            'generated_at': datetime.now().isoformat(),
            'request': request.to_dict(),
            'verification_status': self.get_verification_status(request_id),
            'audit_trail': self.get_audit_trail(request_id),
            'blockchain_stats': self.blockchain.get_blockchain_stats()
        }
        
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        
        return report


# Convenience function for quick verification
def verify_synthetic_data(real_data, synthetic_data,
                          categorical_columns: Optional[List[str]] = None,
                          protected_attributes: Optional[List[str]] = None,
                          target_column: Optional[str] = None,
                          num_verifiers: int = 3) -> Dict:
    """
    Quick verification of synthetic data.
    
    Args:
        real_data: Original dataset
        synthetic_data: Synthetic dataset
        categorical_columns: List of categorical columns
        protected_attributes: List of protected attribute columns
        target_column: Target column for ML tests
        num_verifiers: Number of verifiers for consensus
        
    Returns:
        Verification results with consensus
    """
    orchestrator = VerificationOrchestrator(min_verifiers=num_verifiers)
    
    request_id = orchestrator.submit_for_verification(
        real_data=real_data,
        synthetic_data=synthetic_data,
        categorical_columns=categorical_columns,
        protected_attributes=protected_attributes,
        target_column=target_column
    )
    
    result = orchestrator.run_distributed_verification(request_id, num_verifiers)
    
    return {
        'request_id': request_id,
        'consensus': result,
        'audit_trail': orchestrator.get_audit_trail(request_id)
    }
