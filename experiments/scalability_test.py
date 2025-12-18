"""
Scalability Test Module
Tests system performance with varying dataset sizes and number of verifiers.
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audit_system.privacy_verifier import PrivacyVerifier
from audit_system.utility_verifier import UtilityVerifier
from audit_system.bias_detector import BiasDetector
from audit_system.consensus_engine import ConsensusEngine
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode, compute_data_hash


class ScalabilityTest:
    """
    Tests system scalability across two dimensions:
    1. Dataset size: 1K, 5K, 10K, 50K, 100K rows
    2. Number of verifiers: 1, 3, 5, 7, 10 verifiers
    """
    
    def __init__(self, 
                 base_data: pd.DataFrame,
                 output_dir: str = "results/experiments"):
        """
        Initialize scalability test.
        
        Args:
            base_data: Base dataset to sample from
            output_dir: Directory for results
        """
        self.base_data = base_data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'dataset_size': [],
            'num_verifiers': []
        }
        
    def test_dataset_size(self, 
                          sizes: List[int] = [1000, 5000, 10000, 50000],
                          num_trials: int = 3) -> Dict:
        """
        Test performance with varying dataset sizes.
        
        Args:
            sizes: List of dataset sizes to test
            num_trials: Number of trials per size
            
        Returns:
            Results dictionary
        """
        print("\nTesting Dataset Size Scalability...")
        print("="*60)
        
        results = []
        
        for size in sizes:
            print(f"\nTesting size: {size} rows")
            
            # Limit size to available data
            actual_size = min(size, len(self.base_data))
            
            for trial in range(num_trials):
                # Sample data
                sample_data = self.base_data.sample(n=actual_size, replace=True)
                
                # Create synthetic data (mock)
                synthetic_data = sample_data.copy()
                for col in synthetic_data.select_dtypes(include=[np.number]).columns:
                    synthetic_data[col] = synthetic_data[col] + np.random.normal(0, 0.1, len(synthetic_data))
                
                # Measure verification time
                start_time = time.time()
                
                # Privacy verification
                privacy_verifier = PrivacyVerifier(sample_data, synthetic_data)
                privacy_results = privacy_verifier.verify_all()
                privacy_time = time.time() - start_time
                
                # Utility verification
                util_start = time.time()
                utility_verifier = UtilityVerifier(sample_data, synthetic_data)
                utility_results = utility_verifier.verify_all()
                utility_time = time.time() - util_start
                
                # Bias detection
                bias_start = time.time()
                protected_attrs = [col for col in sample_data.columns 
                                 if any(p in col.lower() for p in ['sex', 'gender', 'race', 'age'])]
                if protected_attrs:
                    bias_detector = BiasDetector(sample_data, synthetic_data, 
                                                protected_attributes=protected_attrs)
                    bias_results = bias_detector.verify_all()
                    bias_time = time.time() - bias_start
                else:
                    bias_time = 0
                
                total_time = time.time() - start_time
                
                results.append({
                    'dataset_size': actual_size,
                    'trial': trial + 1,
                    'total_time': total_time,
                    'privacy_time': privacy_time,
                    'utility_time': utility_time,
                    'bias_time': bias_time,
                    'privacy_score': privacy_results['overall']['privacy_score'],
                    'utility_score': utility_results['overall']['utility_score']
                })
                
                print(f"  Trial {trial + 1}: {total_time:.2f}s")
        
        self.results['dataset_size'] = results
        return self._summarize_size_results(results, sizes)
    
    def test_num_verifiers(self,
                           verifier_counts: List[int] = [1, 3, 5, 7],
                           dataset_size: int = 5000,
                           num_trials: int = 3) -> Dict:
        """
        Test performance with varying number of verifiers.
        
        Args:
            verifier_counts: List of verifier counts to test
            dataset_size: Fixed dataset size
            num_trials: Number of trials per configuration
            
        Returns:
            Results dictionary
        """
        print("\nTesting Number of Verifiers Scalability...")
        print("="*60)
        
        results = []
        
        # Sample fixed dataset
        actual_size = min(dataset_size, len(self.base_data))
        sample_data = self.base_data.sample(n=actual_size, replace=True).reset_index(drop=True)
        synthetic_data = sample_data.copy()
        for col in synthetic_data.select_dtypes(include=[np.number]).columns:
            synthetic_data[col] = synthetic_data[col] + np.random.normal(0, 0.1, len(synthetic_data))
        
        for num_verifiers in verifier_counts:
            print(f"\nTesting {num_verifiers} verifier(s)")
            
            for trial in range(num_trials):
                start_time = time.time()
                
                # Initialize consensus engine
                consensus_engine = ConsensusEngine(min_verifiers=num_verifiers)
                blockchain = BlockchainClient(mode=BlockchainMode.SIMULATION)
                
                data_hash = compute_data_hash(synthetic_data)
                verification_id = consensus_engine.create_verification_request(data_hash)
                
                # Run verifications for each verifier
                verifier_times = []
                submit_result = None
                
                for v in range(num_verifiers):
                    verifier_start = time.time()
                    
                    # Each verifier performs verification
                    privacy_verifier = PrivacyVerifier(sample_data, synthetic_data)
                    privacy_results = privacy_verifier.verify_all()
                    
                    utility_verifier = UtilityVerifier(sample_data, synthetic_data)
                    utility_results = utility_verifier.verify_all()
                    
                    privacy_score = privacy_results['overall']['privacy_score'] + np.random.uniform(-5, 5)
                    utility_score = utility_results['overall']['utility_score'] + np.random.uniform(-5, 5)
                    
                    # Clamp scores
                    privacy_score = max(0, min(100, privacy_score))
                    utility_score = max(0, min(100, utility_score))
                    
                    # Submit verification
                    submit_result = consensus_engine.submit_verification(
                        verification_id=verification_id,
                        verifier_id=f"verifier_{v+1}",
                        privacy_score=privacy_score,
                        utility_score=utility_score,
                        bias_score=80.0  # Default
                    )
                    
                    verifier_times.append(time.time() - verifier_start)
                
                # Blockchain logging - log consensus result
                blockchain_start = time.time()
                if submit_result and 'final_scores' in submit_result:
                    blockchain.log_consensus(
                        data_hash=data_hash,
                        verification_id=verification_id,
                        consensus_result=submit_result
                    )
                if hasattr(blockchain, 'backend') and hasattr(blockchain.backend, 'mine_block'):
                    blockchain.backend.mine_block()
                blockchain_time = time.time() - blockchain_start
                
                # Get final scores from submit_result (consensus triggered automatically)
                final_scores = submit_result.get('final_scores', {}) if submit_result else {}
                
                total_time = time.time() - start_time
                
                results.append({
                    'num_verifiers': num_verifiers,
                    'trial': trial + 1,
                    'total_time': total_time,
                    'avg_verifier_time': np.mean(verifier_times),
                    'blockchain_time': blockchain_time,
                    'consensus_status': submit_result.get('status', 'unknown') if submit_result else 'failed',
                    'final_score': final_scores.get('overall', 0)
                })
                
                print(f"  Trial {trial + 1}: {total_time:.2f}s")
        
        self.results['num_verifiers'] = results
        return self._summarize_verifier_results(results, verifier_counts)
    
    def _summarize_size_results(self, results: List[Dict], sizes: List[int]) -> Dict:
        """Summarize dataset size results."""
        summary = {}
        
        for size in sizes:
            size_results = [r for r in results if r['dataset_size'] == size]
            if size_results:
                times = [r['total_time'] for r in size_results]
                summary[size] = {
                    'mean_time': np.mean(times),
                    'std_time': np.std(times),
                    'min_time': np.min(times),
                    'max_time': np.max(times)
                }
        
        return summary
    
    def _summarize_verifier_results(self, results: List[Dict], counts: List[int]) -> Dict:
        """Summarize verifier count results."""
        summary = {}
        
        for count in counts:
            count_results = [r for r in results if r['num_verifiers'] == count]
            if count_results:
                times = [r['total_time'] for r in count_results]
                summary[count] = {
                    'mean_time': np.mean(times),
                    'std_time': np.std(times),
                    'mean_blockchain_time': np.mean([r['blockchain_time'] for r in count_results])
                }
        
        return summary
    
    def run_all(self) -> Dict:
        """Run all scalability tests."""
        print("\n" + "="*60)
        print("SCALABILITY TEST SUITE")
        print("="*60)
        
        # Test dataset sizes
        size_summary = self.test_dataset_size()
        
        # Test number of verifiers
        verifier_summary = self.test_num_verifiers()
        
        # Save results
        self._save_results()
        
        # Generate plots
        self._generate_plots()
        
        return {
            'dataset_size': size_summary,
            'num_verifiers': verifier_summary
        }
    
    def _save_results(self):
        """Save results to files."""
        # Save dataset size results
        if self.results['dataset_size']:
            df_size = pd.DataFrame(self.results['dataset_size'])
            df_size.to_csv(self.output_dir / 'scalability_dataset_size.csv', index=False)
        
        # Save verifier results
        if self.results['num_verifiers']:
            df_verifiers = pd.DataFrame(self.results['num_verifiers'])
            df_verifiers.to_csv(self.output_dir / 'scalability_verifiers.csv', index=False)
        
        # Save summary
        with open(self.output_dir / 'scalability_summary.json', 'w') as f:
            json.dump({
                'dataset_size_trials': len(self.results['dataset_size']),
                'verifier_trials': len(self.results['num_verifiers']),
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\nResults saved to: {self.output_dir}")
    
    def _generate_plots(self):
        """Generate scalability plots."""
        try:
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            
            # Plot 1: Dataset size vs Time
            if self.results['dataset_size']:
                ax1 = axes[0]
                df = pd.DataFrame(self.results['dataset_size'])
                
                # Group by size and calculate mean
                grouped = df.groupby('dataset_size')['total_time'].agg(['mean', 'std'])
                
                ax1.errorbar(grouped.index, grouped['mean'], yerr=grouped['std'], 
                           marker='o', capsize=5, linewidth=2, markersize=8)
                ax1.set_xlabel('Dataset Size (rows)')
                ax1.set_ylabel('Verification Time (seconds)')
                ax1.set_title('Scalability: Dataset Size vs Time')
                ax1.grid(True, alpha=0.3)
                ax1.set_xscale('log')
            
            # Plot 2: Number of verifiers vs Time
            if self.results['num_verifiers']:
                ax2 = axes[1]
                df = pd.DataFrame(self.results['num_verifiers'])
                
                # Group by verifier count
                grouped = df.groupby('num_verifiers')['total_time'].agg(['mean', 'std'])
                
                ax2.errorbar(grouped.index, grouped['mean'], yerr=grouped['std'],
                           marker='s', capsize=5, linewidth=2, markersize=8, color='green')
                ax2.set_xlabel('Number of Verifiers')
                ax2.set_ylabel('Total Verification Time (seconds)')
                ax2.set_title('Scalability: Number of Verifiers vs Time')
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(self.output_dir / 'scalability_plots.png', dpi=300)
            plt.close()
            
            print(f"Plots saved to: {self.output_dir / 'scalability_plots.png'}")
            
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
    
    def print_summary(self):
        """Print summary of scalability tests."""
        print("\n" + "="*60)
        print("SCALABILITY TEST RESULTS")
        print("="*60)
        
        if self.results['dataset_size']:
            print("\n--- Dataset Size Scalability ---")
            df = pd.DataFrame(self.results['dataset_size'])
            grouped = df.groupby('dataset_size')['total_time'].agg(['mean', 'std'])
            print(grouped.to_string())
        
        if self.results['num_verifiers']:
            print("\n--- Number of Verifiers Scalability ---")
            df = pd.DataFrame(self.results['num_verifiers'])
            grouped = df.groupby('num_verifiers')['total_time'].agg(['mean', 'std'])
            print(grouped.to_string())


def run_scalability_test(data_path: str = None, num_trials: int = 3) -> Dict:
    """
    Convenience function to run scalability tests.
    
    Args:
        data_path: Path to data CSV
        num_trials: Number of trials per configuration
        
    Returns:
        Test results
    """
    if data_path is None:
        data_path = PROJECT_ROOT / "data" / "raw" / "adult.csv"
    
    data = pd.read_csv(data_path)
    
    test = ScalabilityTest(base_data=data)
    results = test.run_all()
    test.print_summary()
    
    return results


if __name__ == "__main__":
    run_scalability_test(num_trials=2)
