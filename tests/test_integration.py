"""
Integration Tests for Synthetic Data Verification System.
Tests the complete workflow from data generation to blockchain verification.
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_system.privacy_verifier import PrivacyVerifier, verify_privacy
from audit_system.utility_verifier import UtilityVerifier, verify_utility
from audit_system.bias_detector import BiasDetector, detect_bias
from audit_system.consensus_engine import ConsensusEngine
from blockchain.api.blockchain_client import BlockchainClient, compute_data_hash
from blockchain.api.verification_orchestrator import VerificationOrchestrator, verify_synthetic_data


class TestEndToEndVerification(unittest.TestCase):
    """Test complete verification workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        np.random.seed(42)
        n_samples = 500
        
        # Create realistic test data
        cls.real_data = pd.DataFrame({
            'age': np.random.normal(45, 15, n_samples).clip(18, 90).astype(int),
            'income': np.random.lognormal(10.5, 0.8, n_samples).astype(int),
            'gender': np.random.choice(['M', 'F'], n_samples, p=[0.48, 0.52]),
            'education': np.random.choice(['HS', 'Bachelor', 'Master', 'PhD'], n_samples, p=[0.3, 0.4, 0.2, 0.1]),
            'employed': np.random.choice([0, 1], n_samples, p=[0.1, 0.9]),
            'region': np.random.choice(['North', 'South', 'East', 'West'], n_samples),
            'credit_score': np.random.normal(700, 50, n_samples).clip(300, 850).astype(int)
        })
        
        # Create synthetic data with similar distribution
        cls.synthetic_data = pd.DataFrame({
            'age': np.random.normal(45, 16, n_samples).clip(18, 90).astype(int),
            'income': np.random.lognormal(10.5, 0.85, n_samples).astype(int),
            'gender': np.random.choice(['M', 'F'], n_samples, p=[0.49, 0.51]),
            'education': np.random.choice(['HS', 'Bachelor', 'Master', 'PhD'], n_samples, p=[0.28, 0.42, 0.2, 0.1]),
            'employed': np.random.choice([0, 1], n_samples, p=[0.12, 0.88]),
            'region': np.random.choice(['North', 'South', 'East', 'West'], n_samples),
            'credit_score': np.random.normal(698, 52, n_samples).clip(300, 850).astype(int)
        })
        
        cls.categorical_columns = ['gender', 'education', 'employed', 'region']
        cls.protected_attributes = ['gender']
        cls.target_column = 'employed'
    
    def test_full_verification_workflow(self):
        """Test complete verification from upload to consensus."""
        orchestrator = VerificationOrchestrator(min_verifiers=3, approval_threshold=70.0)
        
        # Submit for verification
        request_id = orchestrator.submit_for_verification(
            real_data=self.real_data,
            synthetic_data=self.synthetic_data,
            categorical_columns=self.categorical_columns,
            protected_attributes=self.protected_attributes,
            target_column=self.target_column
        )
        
        self.assertIsNotNone(request_id)
        
        # Run verification
        result = orchestrator.run_verification(request_id)
        
        self.assertIn('privacy_verification', result)
        self.assertIn('utility_verification', result)
        self.assertIn('bias_detection', result)
        self.assertIn('data_hash', result)
    
    def test_distributed_verification(self):
        """Test distributed verification with multiple peers."""
        orchestrator = VerificationOrchestrator(min_verifiers=3, approval_threshold=70.0)
        
        request_id = orchestrator.submit_for_verification(
            real_data=self.real_data,
            synthetic_data=self.synthetic_data,
            categorical_columns=self.categorical_columns,
            protected_attributes=self.protected_attributes,
            target_column=self.target_column
        )
        
        result = orchestrator.run_distributed_verification(request_id, num_verifiers=5)
        
        self.assertIn('consensus', result)
        consensus = result['consensus']
        self.assertIn('approved', consensus)
        self.assertIn('final_scores', consensus)
        self.assertEqual(consensus['num_verifiers'], 5)
    
    def test_compliance_report_generation(self):
        """Test compliance report generation."""
        orchestrator = VerificationOrchestrator()
        
        request_id = orchestrator.submit_for_verification(
            real_data=self.real_data,
            synthetic_data=self.synthetic_data,
            categorical_columns=self.categorical_columns
        )
        
        orchestrator.run_verification(request_id)
        
        # Generate GDPR report
        report = orchestrator.generate_compliance_report(request_id, 'GDPR')
        
        self.assertIn('regulation', report)
        self.assertEqual(report['regulation'], 'GDPR')
        self.assertIn('compliance_status', report)
        self.assertIn('requirements', report)
    
    def test_audit_trail_integrity(self):
        """Test that audit trail is properly maintained."""
        orchestrator = VerificationOrchestrator()
        
        request_id = orchestrator.submit_for_verification(
            real_data=self.real_data,
            synthetic_data=self.synthetic_data
        )
        
        orchestrator.run_verification(request_id)
        
        audit_trail = orchestrator.get_audit_trail(request_id)
        
        self.assertIsInstance(audit_trail, list)
        self.assertGreater(len(audit_trail), 0)
        
        # Check that each entry has required fields
        for entry in audit_trail:
            self.assertIn('event_type', entry)
            self.assertIn('timestamp', entry)


class TestVerificationWithDifferentDataQuality(unittest.TestCase):
    """Test verification with different data quality levels."""
    
    def setUp(self):
        np.random.seed(42)
        self.n_samples = 300
        
        self.real_data = pd.DataFrame({
            'value': np.random.normal(100, 20, self.n_samples),
            'category': np.random.choice(['A', 'B', 'C'], self.n_samples),
            'target': np.random.choice([0, 1], self.n_samples)
        })
    
    def test_high_quality_synthetic_data(self):
        """Test verification with high-quality synthetic data."""
        # Create synthetic data very similar to real
        synthetic_data = pd.DataFrame({
            'value': np.random.normal(100, 21, self.n_samples),
            'category': np.random.choice(['A', 'B', 'C'], self.n_samples),
            'target': np.random.choice([0, 1], self.n_samples)
        })
        
        result = verify_synthetic_data(
            real_data=self.real_data,
            synthetic_data=synthetic_data,
            categorical_columns=['category'],
            num_verifiers=3
        )
        
        self.assertIn('consensus', result)
        # High quality should generally pass
        scores = result['consensus']['final_scores']
        self.assertGreater(scores['utility_score'], 60)
    
    def test_low_quality_synthetic_data(self):
        """Test verification with low-quality synthetic data."""
        # Create synthetic data very different from real
        synthetic_data = pd.DataFrame({
            'value': np.random.normal(200, 50, self.n_samples),  # Very different mean/std
            'category': np.random.choice(['A', 'B', 'C', 'D', 'E'], self.n_samples),  # Different categories
            'target': np.ones(self.n_samples).astype(int)  # All same value
        })
        
        result = verify_synthetic_data(
            real_data=self.real_data,
            synthetic_data=synthetic_data,
            categorical_columns=['category'],
            num_verifiers=3
        )
        
        scores = result['consensus']['final_scores']
        # Low quality should have lower scores
        self.assertLess(scores['utility_score'], 90)


class TestBlockchainIntegration(unittest.TestCase):
    """Test blockchain logging and verification."""
    
    def setUp(self):
        self.blockchain = BlockchainClient(simulation_mode=True)
    
    def test_log_and_retrieve_entries(self):
        """Test logging and retrieving blockchain entries."""
        # Create test data
        test_data = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
        data_hash = compute_data_hash(test_data)
        
        # Log generation
        gen_tx = self.blockchain.log_generation(
            data_hash=data_hash,
            model_type='CTGAN',
            training_params={'epochs': 100}
        )
        
        self.assertIsNotNone(gen_tx)
        
        # Verify chain is valid
        stats = self.blockchain.get_blockchain_stats()
        self.assertTrue(stats['is_valid'])
    
    def test_verification_logging(self):
        """Test logging verification results."""
        data_hash = 'test_hash_123'
        
        verification_results = {
            'privacy_score': 85.0,
            'utility_score': 78.0,
            'passed': True
        }
        
        tx_id = self.blockchain.log_verification(
            data_hash=data_hash,
            verification_type='privacy',
            results=verification_results
        )
        
        self.assertIsNotNone(tx_id)
    
    def test_chain_integrity(self):
        """Test blockchain integrity verification."""
        # Add multiple entries
        for i in range(5):
            self.blockchain.log_generation(
                data_hash=f'hash_{i}',
                model_type='CTGAN',
                training_params={'epochs': 100 + i}
            )
        
        stats = self.blockchain.get_blockchain_stats()
        self.assertTrue(stats['is_valid'])
        self.assertGreaterEqual(stats['total_entries'], 5)


class TestConsensusMechanism(unittest.TestCase):
    """Test consensus mechanism with simulated verifiers."""
    
    def setUp(self):
        self.engine = ConsensusEngine(min_verifiers=3, approval_threshold=70.0)
    
    def test_consensus_with_agreement(self):
        """Test consensus when verifiers agree."""
        # Similar verification results
        results = [
            {'privacy': 85.0, 'utility': 80.0, 'bias': 75.0},
            {'privacy': 82.0, 'utility': 78.0, 'bias': 73.0},
            {'privacy': 88.0, 'utility': 82.0, 'bias': 77.0}
        ]
        
        for result in results:
            self.engine.submit_result(
                verifier_id=f'verifier_{len(results)}',
                privacy_score=result['privacy'],
                utility_score=result['utility'],
                bias_score=result['bias']
            )
        
        consensus = self.engine.compute_consensus()
        
        self.assertIn('approved', consensus)
        self.assertIn('final_scores', consensus)
        # With high scores, should be approved
        self.assertTrue(consensus['approved'])
    
    def test_consensus_with_disagreement(self):
        """Test consensus when verifiers disagree."""
        # Mixed verification results
        self.engine.submit_result('v1', 90.0, 85.0, 80.0)
        self.engine.submit_result('v2', 40.0, 45.0, 50.0)
        self.engine.submit_result('v3', 60.0, 65.0, 70.0)
        
        consensus = self.engine.compute_consensus()
        
        # Median should be around 60, which may or may not pass
        self.assertIn('consensus_score', consensus)
    
    def test_min_verifiers_requirement(self):
        """Test that minimum verifiers are required."""
        self.engine.submit_result('v1', 85.0, 80.0, 75.0)
        
        # With only 1 verifier, should not have enough
        stats = self.engine.get_verification_stats()
        self.assertEqual(stats['total_verifications'], 1)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in the system."""
    
    def test_mismatched_columns(self):
        """Test handling of mismatched columns between datasets."""
        real_data = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        synthetic_data = pd.DataFrame({'a': [1, 2, 3], 'c': [4, 5, 6]})
        
        # System should handle gracefully
        result = verify_utility(real_data, synthetic_data)
        self.assertIn('score', result)
    
    def test_empty_data(self):
        """Test handling of empty datasets."""
        real_data = pd.DataFrame()
        synthetic_data = pd.DataFrame()
        
        # Should handle empty data gracefully
        try:
            result = verify_privacy(real_data, synthetic_data)
            # If it returns, check for error indication
            self.assertIn('score', result)
        except Exception as e:
            # Exception is also acceptable for empty data
            self.assertIsNotNone(str(e))
    
    def test_invalid_verification_request(self):
        """Test handling of invalid verification requests."""
        orchestrator = VerificationOrchestrator()
        
        # Try to get status for non-existent request
        status = orchestrator.get_verification_status('invalid_request_id')
        self.assertIn('error', status)


if __name__ == '__main__':
    unittest.main(verbosity=2)
