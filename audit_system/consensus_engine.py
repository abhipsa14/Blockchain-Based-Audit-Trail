"""
Consensus Engine Module
Implements distributed verification with consensus mechanism:
- Multi-peer verification coordination
- Median-based consensus algorithm
- Verification result aggregation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, asdict
import threading
import time


class VerificationStatus(Enum):
    """Status of a verification request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONSENSUS_FAILED = "consensus_failed"


@dataclass
class VerificationResult:
    """Result from a single verifier."""
    verifier_id: str
    privacy_score: float
    utility_score: float
    bias_score: float
    overall_score: float
    timestamp: str
    signature: str
    details: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ConsensusRecord:
    """Aggregated consensus record."""
    data_hash: str
    verification_id: str
    status: VerificationStatus
    final_privacy_score: float
    final_utility_score: float
    final_bias_score: float
    final_overall_score: float
    individual_results: List[VerificationResult]
    consensus_timestamp: str
    threshold_used: float
    num_verifiers: int
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['status'] = self.status.value
        result['individual_results'] = [r.to_dict() if hasattr(r, 'to_dict') else r 
                                        for r in self.individual_results]
        return result


class ConsensusEngine:
    """
    Manages distributed verification and consensus.
    
    Consensus Algorithm:
    1. Collect verification results from N peers (N=3 minimum)
    2. Compute median of overall scores
    3. If median >= 70: Status = APPROVED
    4. If median < 70: Status = REJECTED
    5. Store final status immutably
    """
    
    def __init__(self, min_verifiers: int = 3, approval_threshold: float = 70.0,
                 consensus_timeout: int = 300):
        """
        Initialize the Consensus Engine.
        
        Args:
            min_verifiers: Minimum number of verifiers required
            approval_threshold: Score threshold for approval (0-100)
            consensus_timeout: Timeout in seconds for consensus
        """
        self.min_verifiers = min_verifiers
        self.approval_threshold = approval_threshold
        self.consensus_timeout = consensus_timeout
        
        # Storage for pending verifications
        self.pending_verifications: Dict[str, Dict] = {}
        
        # Storage for completed consensus records
        self.consensus_records: Dict[str, ConsensusRecord] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def create_verification_request(self, data_hash: str, 
                                     metadata: Optional[Dict] = None) -> str:
        """
        Create a new verification request.
        
        Args:
            data_hash: Hash of the data to be verified
            metadata: Optional metadata about the verification
            
        Returns:
            Verification ID
        """
        verification_id = self._generate_verification_id(data_hash)
        
        with self._lock:
            self.pending_verifications[verification_id] = {
                'data_hash': data_hash,
                'created_at': datetime.now().isoformat(),
                'metadata': metadata or {},
                'results': [],
                'status': VerificationStatus.PENDING
            }
        
        return verification_id
    
    def submit_verification(self, verification_id: str, 
                           verifier_id: str,
                           privacy_score: float,
                           utility_score: float,
                           bias_score: float,
                           details: Optional[Dict] = None) -> Dict:
        """
        Submit a verification result from a verifier.
        
        Args:
            verification_id: ID of the verification request
            verifier_id: ID of the verifier submitting results
            privacy_score: Privacy verification score (0-100)
            utility_score: Utility verification score (0-100)
            bias_score: Bias detection score (0-100)
            details: Optional detailed results
            
        Returns:
            Submission status
        """
        if verification_id not in self.pending_verifications:
            return {'error': 'Verification ID not found'}
        
        # Calculate overall score (weighted average)
        overall_score = (
            0.4 * privacy_score +
            0.35 * utility_score +
            0.25 * bias_score
        )
        
        # Create verification result
        result = VerificationResult(
            verifier_id=verifier_id,
            privacy_score=privacy_score,
            utility_score=utility_score,
            bias_score=bias_score,
            overall_score=overall_score,
            timestamp=datetime.now().isoformat(),
            signature=self._sign_result(verifier_id, overall_score),
            details=details or {}
        )
        
        with self._lock:
            # Check for duplicate submissions
            existing_verifiers = [r.verifier_id for r in 
                                 self.pending_verifications[verification_id]['results']]
            if verifier_id in existing_verifiers:
                return {'error': 'Verifier has already submitted results'}
            
            # Add result
            self.pending_verifications[verification_id]['results'].append(result)
            self.pending_verifications[verification_id]['status'] = VerificationStatus.IN_PROGRESS
            
            # Check if we have enough verifiers
            num_results = len(self.pending_verifications[verification_id]['results'])
            
        # Try to reach consensus if we have enough verifiers
        if num_results >= self.min_verifiers:
            return self.attempt_consensus(verification_id)
        
        return {
            'status': 'submitted',
            'verification_id': verification_id,
            'results_received': num_results,
            'results_needed': self.min_verifiers,
            'consensus_reached': False
        }
    
    def attempt_consensus(self, verification_id: str) -> Dict:
        """
        Attempt to reach consensus on a verification.
        
        Args:
            verification_id: ID of the verification request
            
        Returns:
            Consensus result
        """
        if verification_id not in self.pending_verifications:
            return {'error': 'Verification ID not found'}
        
        with self._lock:
            verification = self.pending_verifications[verification_id]
            results = verification['results']
            
            if len(results) < self.min_verifiers:
                return {
                    'error': f'Not enough verifiers. Need {self.min_verifiers}, have {len(results)}'
                }
            
            # Extract scores
            privacy_scores = [r.privacy_score for r in results]
            utility_scores = [r.utility_score for r in results]
            bias_scores = [r.bias_score for r in results]
            overall_scores = [r.overall_score for r in results]
            
            # Compute medians (robust to outliers)
            final_privacy = float(np.median(privacy_scores))
            final_utility = float(np.median(utility_scores))
            final_bias = float(np.median(bias_scores))
            final_overall = float(np.median(overall_scores))
            
            # Check score variance (detect potential attacks)
            score_variance = float(np.var(overall_scores))
            if score_variance > 400:  # Std > 20 points
                # High variance might indicate attack or inconsistent evaluation
                status = VerificationStatus.CONSENSUS_FAILED
            elif final_overall >= self.approval_threshold:
                status = VerificationStatus.APPROVED
            else:
                status = VerificationStatus.REJECTED
            
            # Create consensus record
            consensus_record = ConsensusRecord(
                data_hash=verification['data_hash'],
                verification_id=verification_id,
                status=status,
                final_privacy_score=final_privacy,
                final_utility_score=final_utility,
                final_bias_score=final_bias,
                final_overall_score=final_overall,
                individual_results=results,
                consensus_timestamp=datetime.now().isoformat(),
                threshold_used=self.approval_threshold,
                num_verifiers=len(results)
            )
            
            # Store consensus record
            self.consensus_records[verification_id] = consensus_record
            
            # Remove from pending
            del self.pending_verifications[verification_id]
        
        return {
            'consensus_reached': True,
            'verification_id': verification_id,
            'status': status.value,
            'final_scores': {
                'privacy': final_privacy,
                'utility': final_utility,
                'bias': final_bias,
                'overall': final_overall
            },
            'score_variance': score_variance,
            'num_verifiers': len(results),
            'threshold': self.approval_threshold
        }
    
    def query_consensus(self, verification_id: str) -> Optional[Dict]:
        """
        Query the consensus result for a verification.
        
        Args:
            verification_id: ID of the verification request
            
        Returns:
            Consensus record if available
        """
        if verification_id in self.consensus_records:
            return self.consensus_records[verification_id].to_dict()
        
        if verification_id in self.pending_verifications:
            verification = self.pending_verifications[verification_id]
            return {
                'status': verification['status'].value,
                'results_received': len(verification['results']),
                'results_needed': self.min_verifiers,
                'consensus_reached': False
            }
        
        return None
    
    def query_by_data_hash(self, data_hash: str) -> List[Dict]:
        """
        Query all consensus records for a data hash.
        
        Args:
            data_hash: Hash of the data
            
        Returns:
            List of consensus records
        """
        records = []
        for record in self.consensus_records.values():
            if record.data_hash == data_hash:
                records.append(record.to_dict())
        return records
    
    def verify_integrity(self, verification_id: str, 
                        expected_scores: Dict[str, float]) -> Dict:
        """
        Verify the integrity of a consensus record.
        
        Args:
            verification_id: ID of the verification
            expected_scores: Expected score values
            
        Returns:
            Integrity check result
        """
        if verification_id not in self.consensus_records:
            return {'valid': False, 'error': 'Record not found'}
        
        record = self.consensus_records[verification_id]
        
        # Check scores match
        scores_match = (
            abs(record.final_privacy_score - expected_scores.get('privacy', 0)) < 0.01 and
            abs(record.final_utility_score - expected_scores.get('utility', 0)) < 0.01 and
            abs(record.final_bias_score - expected_scores.get('bias', 0)) < 0.01 and
            abs(record.final_overall_score - expected_scores.get('overall', 0)) < 0.01
        )
        
        # Verify signatures
        signatures_valid = all(
            self._verify_signature(r.verifier_id, r.overall_score, r.signature)
            for r in record.individual_results
        )
        
        return {
            'valid': scores_match and signatures_valid,
            'scores_match': scores_match,
            'signatures_valid': signatures_valid,
            'record': record.to_dict()
        }
    
    def get_verification_stats(self) -> Dict:
        """Get statistics about verifications."""
        total_completed = len(self.consensus_records)
        total_pending = len(self.pending_verifications)
        
        if total_completed > 0:
            approved = sum(1 for r in self.consensus_records.values() 
                         if r.status == VerificationStatus.APPROVED)
            rejected = sum(1 for r in self.consensus_records.values() 
                          if r.status == VerificationStatus.REJECTED)
            failed = sum(1 for r in self.consensus_records.values() 
                        if r.status == VerificationStatus.CONSENSUS_FAILED)
            
            avg_privacy = np.mean([r.final_privacy_score for r in self.consensus_records.values()])
            avg_utility = np.mean([r.final_utility_score for r in self.consensus_records.values()])
            avg_bias = np.mean([r.final_bias_score for r in self.consensus_records.values()])
        else:
            approved = rejected = failed = 0
            avg_privacy = avg_utility = avg_bias = 0
        
        return {
            'total_completed': total_completed,
            'total_pending': total_pending,
            'approved': approved,
            'rejected': rejected,
            'consensus_failed': failed,
            'approval_rate': approved / total_completed if total_completed > 0 else 0,
            'average_scores': {
                'privacy': float(avg_privacy),
                'utility': float(avg_utility),
                'bias': float(avg_bias)
            }
        }
    
    def _generate_verification_id(self, data_hash: str) -> str:
        """Generate unique verification ID."""
        timestamp = datetime.now().isoformat()
        combined = f"{data_hash}:{timestamp}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _sign_result(self, verifier_id: str, score: float) -> str:
        """Sign a verification result (simplified version)."""
        # In production, this would use proper cryptographic signing
        combined = f"{verifier_id}:{score}:{datetime.now().isoformat()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    def _verify_signature(self, verifier_id: str, score: float, signature: str) -> bool:
        """Verify a signature (simplified version)."""
        # In production, this would use proper cryptographic verification
        # For now, just check signature format
        return len(signature) == 32 and signature.isalnum()
    
    def export_records(self) -> List[Dict]:
        """Export all consensus records."""
        return [record.to_dict() for record in self.consensus_records.values()]
    
    def import_records(self, records: List[Dict]) -> int:
        """Import consensus records (for persistence)."""
        imported = 0
        for record_dict in records:
            try:
                # Convert status string back to enum
                record_dict['status'] = VerificationStatus(record_dict['status'])
                
                # Convert individual results
                individual_results = []
                for r in record_dict['individual_results']:
                    individual_results.append(VerificationResult(**r))
                record_dict['individual_results'] = individual_results
                
                # Create record
                record = ConsensusRecord(**record_dict)
                self.consensus_records[record.verification_id] = record
                imported += 1
            except Exception as e:
                print(f"Error importing record: {e}")
        
        return imported


class SimulatedVerifier:
    """
    Simulated verifier for testing consensus mechanism.
    """
    
    def __init__(self, verifier_id: str, bias: float = 0.0, noise: float = 5.0):
        """
        Initialize simulated verifier.
        
        Args:
            verifier_id: Unique verifier identifier
            bias: Systematic bias in scores (-10 to +10)
            noise: Random noise level in scores
        """
        self.verifier_id = verifier_id
        self.bias = bias
        self.noise = noise
    
    def verify(self, true_privacy: float, true_utility: float, 
               true_bias: float) -> Tuple[float, float, float]:
        """
        Simulate verification with noise and bias.
        
        Args:
            true_privacy: True privacy score
            true_utility: True utility score
            true_bias: True bias score
            
        Returns:
            Tuple of (privacy, utility, bias) scores with noise
        """
        privacy = np.clip(true_privacy + self.bias + np.random.normal(0, self.noise), 0, 100)
        utility = np.clip(true_utility + self.bias + np.random.normal(0, self.noise), 0, 100)
        bias = np.clip(true_bias + self.bias + np.random.normal(0, self.noise), 0, 100)
        
        return float(privacy), float(utility), float(bias)


def simulate_consensus(true_scores: Dict[str, float], 
                       num_verifiers: int = 5,
                       noise_level: float = 5.0) -> Dict:
    """
    Simulate a consensus process.
    
    Args:
        true_scores: Dictionary with true privacy, utility, bias scores
        num_verifiers: Number of verifiers to simulate
        noise_level: Noise level for each verifier
        
    Returns:
        Consensus result
    """
    engine = ConsensusEngine(min_verifiers=num_verifiers)
    
    # Create verification request
    data_hash = hashlib.sha256(str(true_scores).encode()).hexdigest()
    verification_id = engine.create_verification_request(data_hash)
    
    # Create simulated verifiers with varying biases
    verifiers = [
        SimulatedVerifier(f"verifier_{i}", 
                         bias=np.random.uniform(-3, 3),
                         noise=noise_level)
        for i in range(num_verifiers)
    ]
    
    # Submit verifications
    for verifier in verifiers:
        privacy, utility, bias = verifier.verify(
            true_scores['privacy'],
            true_scores['utility'],
            true_scores['bias']
        )
        
        engine.submit_verification(
            verification_id=verification_id,
            verifier_id=verifier.verifier_id,
            privacy_score=privacy,
            utility_score=utility,
            bias_score=bias
        )
    
    # Get consensus result
    return engine.query_consensus(verification_id)
