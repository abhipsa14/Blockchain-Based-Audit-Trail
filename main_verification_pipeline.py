"""
Main Verification Pipeline
End-to-end workflow for synthetic data generation and verification.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / '.env')
sys.path.insert(0, str(PROJECT_ROOT))

from audit_system.privacy_verifier import PrivacyVerifier, verify_privacy
from audit_system.utility_verifier import UtilityVerifier, verify_utility
from audit_system.bias_detector import BiasDetector, detect_bias
from audit_system.consensus_engine import ConsensusEngine, VerificationStatus
from audit_system.compliance_checker import ComplianceChecker, check_compliance
from audit_system.logger import AuditLogger, AuditEventType, LogLevel, get_logger
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode, compute_data_hash
from blockchain.api.verification_orchestrator import VerificationOrchestrator
from ml_models.generators.auditable_ctgan import AuditableCTGAN


class VerificationPipeline:
    """
    End-to-end verification pipeline for synthetic data.
    
    Workflow:
    1. Load or generate synthetic data
    2. Run privacy verification
    3. Run utility verification
    4. Run bias detection
    5. Gather consensus from multiple verifiers
    6. Check regulatory compliance
    7. Log to blockchain
    8. Generate comprehensive report
    """
    
    def __init__(self, 
                 num_verifiers: int = 3,
                 approval_threshold: float = 70.0,
                 log_dir: str = "logs",
                 results_dir: str = "results"):
        """
        Initialize the verification pipeline.
        
        Args:
            num_verifiers: Number of verifiers for consensus
            approval_threshold: Score threshold for approval (0-100)
            log_dir: Directory for logs
            results_dir: Directory for results
        """
        self.num_verifiers = num_verifiers
        self.approval_threshold = approval_threshold
        
        # Create directories
        self.log_dir = Path(log_dir)
        self.results_dir = Path(results_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.results_dir / "metrics").mkdir(exist_ok=True)
        (self.results_dir / "plots").mkdir(exist_ok=True)
        (self.results_dir / "reports").mkdir(exist_ok=True)
        
        # Initialize components
        self.logger = AuditLogger(log_dir=str(self.log_dir))
        self.blockchain = BlockchainClient(mode=BlockchainMode.SIMULATION)
        self.consensus_engine = ConsensusEngine(
            min_verifiers=num_verifiers,
            approval_threshold=approval_threshold
        )
        
        # Pipeline state
        self.real_data = None
        self.synthetic_data = None
        self.results = {}
        self.real_data_path = None  # Store for cache path detection
        
    def _get_cache_path_for_dataset(self, data_path: str) -> str:
        """Get the appropriate cache path based on the dataset being used."""
        data_path_lower = data_path.lower()
        
        if 'adult' in data_path_lower:
            return str(self.results_dir / "cached_ctgan_adult.pkl")
        elif 'healthcare' in data_path_lower:
            return str(self.results_dir / "cached_ctgan_healthcare.pkl")
        else:
            # Generate cache path from filename
            filename = Path(data_path).stem
            return str(self.results_dir / f"cached_ctgan_{filename}.pkl")
        
    def load_data(self, 
                  real_data_path: str,
                  synthetic_data_path: str = None,
                  generate_synthetic: bool = False,
                  categorical_columns: list = None,
                  num_synthetic_rows: int = None,
                  force_retrain: bool = False) -> dict:
        """
        Load real data and optionally generate synthetic data.
        
        Args:
            real_data_path: Path to real dataset (CSV)
            synthetic_data_path: Path to synthetic dataset (if pre-generated)
            generate_synthetic: Whether to generate synthetic data
            categorical_columns: List of categorical columns
            num_synthetic_rows: Number of synthetic rows to generate
            force_retrain: If True, ignore cached model and retrain (default: False)
            
        Returns:
            Dictionary with data loading results
        """
        self.logger.start_session(actor="pipeline")
        self.real_data_path = real_data_path  # Store for cache path detection
        
        # Load real data
        print(f"Loading real data from: {real_data_path}")
        self.real_data = pd.read_csv(real_data_path)
        real_hash = compute_data_hash(self.real_data)
        
        self.logger.log(
            event_type=AuditEventType.DATA_UPLOAD,
            level=LogLevel.INFO,
            actor="pipeline",
            action="load_real_data",
            resource=real_data_path,
            resource_hash=real_hash,
            details={
                'rows': len(self.real_data),
                'columns': list(self.real_data.columns),
                'path': real_data_path
            }
        )
        
        # Load or generate synthetic data
        if synthetic_data_path and os.path.exists(synthetic_data_path):
            print(f"Loading synthetic data from: {synthetic_data_path}")
            self.synthetic_data = pd.read_csv(synthetic_data_path)
            synth_hash = compute_data_hash(self.synthetic_data)
            
            self.logger.log(
                event_type=AuditEventType.DATA_UPLOAD,
                level=LogLevel.INFO,
                actor="pipeline",
                action="load_synthetic_data",
                resource=synthetic_data_path,
                resource_hash=synth_hash,
                details={
                    'rows': len(self.synthetic_data),
                    'columns': list(self.synthetic_data.columns)
                }
            )
            
        elif generate_synthetic:
            print("Generating synthetic data...")
            self.synthetic_data, generation_log = self._generate_synthetic_data(
                categorical_columns=categorical_columns,
                num_rows=num_synthetic_rows or len(self.real_data),
                force_retrain=force_retrain
            )
            synth_hash = compute_data_hash(self.synthetic_data)
            
            self.logger.log_generation(
                generator_type="CTGAN",
                input_hash=real_hash,
                output_hash=synth_hash,
                num_rows=len(self.synthetic_data),
                hyperparameters=generation_log.get('hyperparameters', {}),
                actor="pipeline"
            )
        else:
            raise ValueError("Either provide synthetic_data_path or set generate_synthetic=True")
        
        return {
            'real_data_shape': self.real_data.shape,
            'synthetic_data_shape': self.synthetic_data.shape,
            'real_data_hash': real_hash,
            'synthetic_data_hash': synth_hash,
            'columns': list(self.real_data.columns)
        }
    
    def _generate_synthetic_data(self, 
                                  categorical_columns: list = None,
                                  num_rows: int = None,
                                  model_path: str = None,
                                  save_model: bool = True,
                                  force_retrain: bool = False) -> tuple:
        """Generate synthetic data using CTGAN with model caching to avoid retraining.
        
        The model is cached after training. On subsequent runs, the cached model
        is loaded directly, skipping the time-consuming training process.
        
        Args:
            categorical_columns: List of categorical columns
            num_rows: Number of synthetic rows to generate
            model_path: Custom path for model cache
            save_model: Whether to save the trained model
            force_retrain: If True, ignore cache and retrain (default: False)
        """
        # Use dataset-specific cache path
        model_cache_path = model_path or self._get_cache_path_for_dataset(self.real_data_path)
        ctgan_cache_path = model_cache_path.replace('.pkl', '_ctgan.pkl')
        
        print(f"[CACHE] Using cache path: {model_cache_path}")
        
        # Compute hash of current input data to validate cache
        current_data_hash = compute_data_hash(self.real_data)
        
        # Auto-detect categorical columns if not provided
        if categorical_columns is None:
            categorical_columns = []
            for col in self.real_data.columns:
                if (self.real_data[col].dtype == 'object' or 
                    self.real_data[col].nunique() < 20):
                    categorical_columns.append(col)
        
        generator = None
        cache_valid = False
        
        # Try to load existing model (skip if force_retrain is True)
        if not force_retrain and os.path.exists(model_cache_path) and os.path.exists(ctgan_cache_path):
            try:
                print(f"[CACHE] Found cached model at: {model_cache_path}")
                generator = AuditableCTGAN.load(model_cache_path, verbose=True)
                
                # Validate that cached model matches current data structure
                if (generator.columns == list(self.real_data.columns) and 
                    set(generator.categorical_columns) == set(categorical_columns)):
                    cache_valid = True
                    print(f"[CACHE] Model loaded successfully! Skipping training.")
                    print(f"[CACHE] Original training hash: {generator.training_data_hash[:16]}...")
                else:
                    print(f"[CACHE] Column mismatch detected. Will retrain model.")
                    generator = None
                    
            except Exception as e:
                print(f"[CACHE] Failed to load cached model: {e}")
                print(f"[CACHE] Will train a new model.")
                generator = None
        
        # Train new model if cache is invalid or doesn't exist
        if generator is None or not cache_valid:
            print(f"\n[TRAINING] Starting CTGAN training (this may take a while)...")
            print(f"[TRAINING] Dataset: {len(self.real_data)} rows, {len(self.real_data.columns)} columns")
            print(f"[TRAINING] Categorical columns: {categorical_columns}")
            
            generator = AuditableCTGAN(
                epochs=100,  # Reduced for faster execution
                batch_size=500,
                verbose=True
            )
            
            # Train model
            generator.fit(self.real_data, discrete_columns=categorical_columns)
            
            # Save model for future use
            if save_model:
                generator.save(model_cache_path)
                print(f"[CACHE] Model saved to: {model_cache_path}")
                print(f"[CACHE] Next run will load from cache (no training needed)!")
        
        # Generate synthetic data (this is fast even without cache)
        print(f"\n[GENERATING] Creating {num_rows or len(self.real_data)} synthetic samples...")
        synthetic_data = generator.sample(num_rows or len(self.real_data))
        audit_log = generator.get_latest_audit_log()
        
        return synthetic_data, audit_log
    
    def run_verification(self,
                         categorical_columns: list = None,
                         protected_attributes: list = None,
                         target_column: str = None,
                         sensitive_columns: list = None) -> dict:
        """
        Run complete verification pipeline.
        
        Args:
            categorical_columns: List of categorical columns
            protected_attributes: List of protected attribute columns for bias detection
            target_column: Target column for ML efficacy tests
            sensitive_columns: Sensitive columns for privacy verification
            
        Returns:
            Complete verification results
        """
        if self.real_data is None or self.synthetic_data is None:
            raise ValueError("Load data first using load_data()")
        
        print("\n" + "="*60)
        print("STARTING VERIFICATION PIPELINE")
        print("="*60)
        
        data_hash = compute_data_hash(self.synthetic_data)
        
        # Auto-detect columns if not provided
        if categorical_columns is None:
            categorical_columns = [col for col in self.real_data.columns
                                   if self.real_data[col].dtype == 'object' or 
                                   self.real_data[col].nunique() < 20]
        
        if protected_attributes is None:
            # Common protected attribute names
            possible_protected = ['sex', 'gender', 'race', 'ethnicity', 'age', 'religion']
            protected_attributes = [col for col in self.real_data.columns 
                                    if any(p in col.lower() for p in possible_protected)]
        
        # 1. Privacy Verification
        print("\n[1/4] Running Privacy Verification...")
        privacy_results = self._run_privacy_verification(sensitive_columns)
        self.results['privacy'] = privacy_results
        print(f"      Privacy Score: {privacy_results['overall']['privacy_score']:.2f}%")
        
        # 2. Utility Verification
        print("\n[2/4] Running Utility Verification...")
        utility_results = self._run_utility_verification(categorical_columns, target_column)
        self.results['utility'] = utility_results
        print(f"      Utility Score: {utility_results['overall']['utility_score']:.2f}%")
        
        # 3. Bias Detection
        print("\n[3/4] Running Bias Detection...")
        bias_results = self._run_bias_detection(protected_attributes, target_column)
        self.results['bias'] = bias_results
        print(f"      Fairness Score: {bias_results['overall']['fairness_score']:.2f}%")
        
        # 4. Consensus
        print("\n[4/4] Gathering Consensus...")
        consensus_results = self._run_consensus(data_hash)
        self.results['consensus'] = consensus_results
        print(f"      Consensus Status: {consensus_results['status']}")
        print(f"      Final Score: {consensus_results['final_score']:.2f}%")
        
        # Log results to blockchain
        self.blockchain.log_verification(
            data_hash=data_hash,
            verification_id="pipeline-complete",
            verifier_id="pipeline",
            results={
                'privacy_score': privacy_results['overall']['privacy_score'],
                'utility_score': utility_results['overall']['utility_score'],
                'fairness_score': bias_results['overall']['fairness_score'],
                'overall_score': consensus_results['final_score']
            }
        )
        
        print("\n" + "="*60)
        print("VERIFICATION COMPLETE")
        print("="*60)
        
        return self.results
    
    def _run_privacy_verification(self, sensitive_columns: list = None) -> dict:
        """Run privacy verification."""
        verifier = PrivacyVerifier(
            self.real_data, 
            self.synthetic_data,
            sensitive_columns=sensitive_columns
        )
        results = verifier.verify_all()
        
        self.logger.log_verification(
            verification_type="privacy",
            data_hash=compute_data_hash(self.synthetic_data),
            score=results['overall']['privacy_score'],
            passed=results['overall']['privacy_score'] >= self.approval_threshold,
            details=results,
            actor="pipeline"
        )
        
        return results
    
    def _run_utility_verification(self, categorical_columns: list, target_column: str) -> dict:
        """Run utility verification."""
        verifier = UtilityVerifier(
            self.real_data,
            self.synthetic_data,
            categorical_columns=categorical_columns,
            target_column=target_column
        )
        results = verifier.verify_all()
        
        self.logger.log_verification(
            verification_type="utility",
            data_hash=compute_data_hash(self.synthetic_data),
            score=results['overall']['utility_score'],
            passed=results['overall']['utility_score'] >= self.approval_threshold,
            details=results,
            actor="pipeline"
        )
        
        return results
    
    def _run_bias_detection(self, protected_attributes: list, target_column: str) -> dict:
        """Run bias detection."""
        detector = BiasDetector(
            self.real_data,
            self.synthetic_data,
            protected_attributes=protected_attributes,
            target_column=target_column
        )
        results = detector.verify_all()
        
        self.logger.log_verification(
            verification_type="bias",
            data_hash=compute_data_hash(self.synthetic_data),
            score=results['overall']['fairness_score'],
            passed=results['overall']['fairness_score'] >= self.approval_threshold,
            details=results,
            actor="pipeline"
        )
        
        return results
    
    def _run_consensus(self, data_hash: str) -> dict:
        """Run consensus mechanism with multiple verifiers."""
        # Create verification request and store the verification_id
        verification_id = self.consensus_engine.create_verification_request(
            data_hash=data_hash,
            metadata={'pipeline': 'main'}
        )
        
        # Simulate multiple verifiers
        for i in range(self.num_verifiers):
            verifier_id = f"verifier_{i+1}"
            
            # Add small variations to simulate independent verification
            privacy_variation = np.random.uniform(-5, 5)
            utility_variation = np.random.uniform(-5, 5)
            bias_variation = np.random.uniform(-5, 5)
            
            privacy_score = min(100, max(0, self.results['privacy']['overall']['privacy_score'] + privacy_variation))
            utility_score = min(100, max(0, self.results['utility']['overall']['utility_score'] + utility_variation))
            bias_score = min(100, max(0, self.results['bias']['overall']['fairness_score'] + bias_variation))
            
            self.consensus_engine.submit_verification(
                verification_id=verification_id,
                verifier_id=verifier_id,
                privacy_score=privacy_score,
                utility_score=utility_score,
                bias_score=bias_score,
                details={
                    'privacy': {'score': privacy_score},
                    'utility': {'score': utility_score},
                    'bias': {'score': bias_score}
                }
            )
        
        # Attempt to reach consensus
        consensus_result = self.consensus_engine.attempt_consensus(verification_id)
        
        # Query the full consensus record
        consensus_record = self.consensus_engine.consensus_records.get(verification_id)
        
        if consensus_record is None:
            # Fallback if consensus failed
            result = {
                'status': 'CONSENSUS_FAILED',
                'final_score': 0,
                'privacy_score': self.results['privacy']['overall']['privacy_score'],
                'utility_score': self.results['utility']['overall']['utility_score'],
                'bias_score': self.results['bias']['overall']['fairness_score'],
                'num_verifiers': self.num_verifiers,
                'threshold': self.approval_threshold
            }
        else:
            result = {
                'status': consensus_record.status.value,
                'final_score': consensus_record.final_overall_score,
                'privacy_score': consensus_record.final_privacy_score,
                'utility_score': consensus_record.final_utility_score,
                'bias_score': consensus_record.final_bias_score,
                'num_verifiers': consensus_record.num_verifiers,
                'threshold': self.approval_threshold
            }
        
        self.logger.log_consensus(
            data_hash=data_hash,
            status=result['status'],
            scores={
                'privacy': result['privacy_score'],
                'utility': result['utility_score'],
                'bias': result['bias_score'],
                'overall': result['final_score']
            },
            num_verifiers=result['num_verifiers'],
            actor="pipeline"
        )
        
        return result
    
    def check_compliance(self, standard: str = 'all') -> dict:
        """
        Check regulatory compliance.
        
        Args:
            standard: Compliance standard ('gdpr', 'hipaa', 'eu_ai_act', 'all')
            
        Returns:
            Compliance report
        """
        if not self.results:
            raise ValueError("Run verification first using run_verification()")
        
        print("\n" + "="*60)
        print("CHECKING REGULATORY COMPLIANCE")
        print("="*60)
        
        compliance_report = check_compliance(
            real_data=self.real_data,
            synthetic_data=self.synthetic_data,
            privacy_score=self.results['privacy']['overall']['privacy_score'],
            utility_score=self.results['utility']['overall']['utility_score'],
            bias_score=self.results['bias']['overall']['fairness_score'],
            audit_log=self.logger.get_summary(),
            standard=standard
        )
        
        self.results['compliance'] = compliance_report
        
        print(f"Overall Compliance Score: {compliance_report['compliance']['overall_compliance_score']:.2f}%")
        print(f"GDPR Compliant: {compliance_report['compliance']['gdpr']['compliant']}")
        print(f"HIPAA Compliant: {compliance_report['compliance']['hipaa']['compliant']}")
        print(f"EU AI Act Compliant: {compliance_report['compliance']['eu_ai_act']['compliant']}")
        
        return compliance_report
    
    def generate_report(self, output_path: str = None) -> dict:
        """
        Generate comprehensive verification report.
        
        Args:
            output_path: Path to save the report (optional)
            
        Returns:
            Complete report dictionary
        """
        if not self.results:
            raise ValueError("Run verification first using run_verification()")
        
        report = {
            'report_id': compute_data_hash(self.synthetic_data)[:16],
            'generated_at': datetime.now().isoformat(),
            'pipeline_config': {
                'num_verifiers': self.num_verifiers,
                'approval_threshold': self.approval_threshold
            },
            'data_summary': {
                'real_data_shape': list(self.real_data.shape),
                'synthetic_data_shape': list(self.synthetic_data.shape),
                'columns': list(self.real_data.columns)
            },
            'verification_results': {
                'privacy': {
                    'score': self.results['privacy']['overall']['privacy_score'],
                    'passed': self.results['privacy']['overall']['privacy_score'] >= self.approval_threshold,
                    'details': self.results['privacy']
                },
                'utility': {
                    'score': self.results['utility']['overall']['utility_score'],
                    'passed': self.results['utility']['overall']['utility_score'] >= self.approval_threshold,
                    'details': self.results['utility']
                },
                'bias': {
                    'score': self.results['bias']['overall']['fairness_score'],
                    'passed': self.results['bias']['overall']['fairness_score'] >= self.approval_threshold,
                    'details': self.results['bias']
                }
            },
            'consensus': self.results.get('consensus', {}),
            'compliance': self.results.get('compliance', {}),
            'blockchain': {
                'stats': self.blockchain.get_blockchain_stats(),
                'entries': len(self.blockchain.simulated_blockchain.entry_index) if hasattr(self.blockchain, 'simulated_blockchain') else 0
            },
            'audit_summary': self.logger.get_summary()
        }
        
        # Calculate overall status
        overall_passed = all([
            self.results['privacy']['overall']['privacy_score'] >= self.approval_threshold,
            self.results['utility']['overall']['utility_score'] >= self.approval_threshold,
            self.results['bias']['overall']['fairness_score'] >= self.approval_threshold
        ])
        
        report['overall_status'] = 'APPROVED' if overall_passed else 'REJECTED'
        report['overall_score'] = (
            self.results['privacy']['overall']['privacy_score'] +
            self.results['utility']['overall']['utility_score'] +
            self.results['bias']['overall']['fairness_score']
        ) / 3
        
        # Save report
        if output_path is None:
            output_path = self.results_dir / "reports" / f"verification_report_{report['report_id']}.json"
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\nReport saved to: {output_path}")
        
        return report
    
    def end_pipeline(self) -> dict:
        """End the pipeline and finalize logging."""
        # Mine pending blockchain entries
        if hasattr(self.blockchain, 'backend') and hasattr(self.blockchain.backend, 'mine_block'):
            self.blockchain.backend.mine_block()
        
        # End audit session
        session_summary = self.logger.end_session()
        
        # Export audit trail
        audit_export_path = self.logger.export_audit_trail(
            format='json',
            filepath=str(self.results_dir / "reports" / f"audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        )
        
        print(f"\nAudit trail exported to: {audit_export_path}")
        
        return {
            'session_summary': session_summary,
            'audit_export': audit_export_path,
            'blockchain_stats': self.blockchain.get_blockchain_stats()
        }


def main():
    """Main entry point for the verification pipeline."""
    default_real_data = os.getenv('DEFAULT_REAL_DATA', 'data/raw/adult.csv')
    default_num_verifiers = int(os.getenv('VERIFICATION_MIN_VERIFIERS', '3'))
    default_threshold = float(os.getenv('VERIFICATION_APPROVAL_THRESHOLD', '70.0'))
    default_target_column = os.getenv('DEFAULT_TARGET_COLUMN', 'income')

    parser = argparse.ArgumentParser(
        description='Synthetic Data Verification Pipeline'
    )
    parser.add_argument(
        '--real-data',
        type=str,
        default=default_real_data,
        help='Path to real data CSV'
    )
    parser.add_argument(
        '--synthetic-data',
        type=str,
        default=None,
        help='Path to synthetic data CSV (optional)'
    )
    parser.add_argument(
        '--generate',
        action='store_true',
        help='Generate synthetic data if not provided'
    )
    parser.add_argument(
        '--num-rows',
        type=int,
        default=None,
        help='Number of synthetic rows to generate'
    )
    parser.add_argument(
        '--num-verifiers',
        type=int,
        default=default_num_verifiers,
        help='Number of verifiers for consensus'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=default_threshold,
        help='Approval threshold (0-100)'
    )
    parser.add_argument(
        '--target-column',
        type=str,
        default=default_target_column,
        help='Target column for ML efficacy tests'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for report'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Force retraining, ignore cached model'
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Delete cached model files'
    )
    parser.add_argument(
        '--save-synthetic',
        type=str,
        default=None,
        help='Path to save generated synthetic data'
    )
    
    args = parser.parse_args()
    
    # Delete cached model files if --clear-cache specified
    if args.clear_cache:
        cache_files = [
            Path("results/cached_ctgan_model.pkl"),
            Path("results/cached_ctgan_model_ctgan.pkl")
        ]
        for cache_path in cache_files:
            if cache_path.exists():
                cache_path.unlink()
                print(f"Deleted cache file: {cache_path}")
        print("Cache cleared successfully.")
    
    # Initialize pipeline
    pipeline = VerificationPipeline(
        num_verifiers=args.num_verifiers,
        approval_threshold=args.threshold
    )
    
    try:
        # Load data
        print("\n" + "="*60)
        print("LOADING DATA")
        print("="*60)
        
        data_info = pipeline.load_data(
            real_data_path=args.real_data,
            synthetic_data_path=args.synthetic_data,
            generate_synthetic=args.generate or args.synthetic_data is None,
            num_synthetic_rows=args.num_rows,
            force_retrain=args.no_cache
        )
        
        print(f"Real data shape: {data_info['real_data_shape']}")
        print(f"Synthetic data shape: {data_info['synthetic_data_shape']}")
        
        # Save synthetic data if requested
        if args.save_synthetic and pipeline.synthetic_data is not None:
            pipeline.synthetic_data.to_csv(args.save_synthetic, index=False)
            print(f"Synthetic data saved to: {args.save_synthetic}")
        
        # Run verification
        verification_results = pipeline.run_verification(
            target_column=args.target_column
        )
        
        # Check compliance
        compliance_report = pipeline.check_compliance()
        
        # Generate report
        report = pipeline.generate_report(output_path=args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"Overall Status: {report['overall_status']}")
        print(f"Overall Score: {report['overall_score']:.2f}%")
        print(f"Privacy Score: {report['verification_results']['privacy']['score']:.2f}%")
        print(f"Utility Score: {report['verification_results']['utility']['score']:.2f}%")
        print(f"Bias Score: {report['verification_results']['bias']['score']:.2f}%")
        
        # End pipeline
        pipeline.end_pipeline()
        
        return report
        
    except Exception as e:
        print(f"\nError: {e}")
        pipeline.logger.log_error(
            error_type=type(e).__name__,
            error_message=str(e),
            details={'traceback': str(e)},
            actor="pipeline"
        )
        raise


if __name__ == "__main__":
    main()
