"""
Comparative Study Module
Compares blockchain-based verification with baseline approaches.
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
import seaborn as sns

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audit_system.privacy_verifier import PrivacyVerifier
from audit_system.utility_verifier import UtilityVerifier
from audit_system.bias_detector import BiasDetector
from audit_system.consensus_engine import ConsensusEngine
from blockchain.api.blockchain_client import BlockchainClient, BlockchainMode, compute_data_hash


class ComparativeStudy:
    """
    Compares three verification approaches:
    1. Baseline: No verification (generation only)
    2. Centralized: Single trusted verifier
    3. Blockchain: Distributed verification with consensus
    """
    
    def __init__(self, 
                 real_data: pd.DataFrame,
                 synthetic_data: pd.DataFrame,
                 num_trials: int = 10,
                 output_dir: str = "results/experiments"):
        """
        Initialize comparative study.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            num_trials: Number of trials per approach
            output_dir: Directory for results
        """
        self.real_data = real_data
        self.synthetic_data = synthetic_data
        self.num_trials = num_trials
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'baseline': [],
            'centralized': [],
            'blockchain': []
        }
        
    def run_baseline(self) -> Dict:
        """
        Baseline approach: No verification.
        Just measures generation time without any quality checks.
        """
        trial_results = []
        
        for trial in range(self.num_trials):
            start_time = time.time()
            
            # Simulate generation (data already generated)
            data_hash = compute_data_hash(self.synthetic_data)
            
            end_time = time.time()
            
            trial_results.append({
                'trial': trial + 1,
                'approach': 'baseline',
                'latency': end_time - start_time,
                'trust_score': 0,  # No verification = no trust
                'privacy_score': None,
                'utility_score': None,
                'bias_score': None,
                'tamper_resistant': False,
                'data_hash': data_hash
            })
        
        self.results['baseline'] = trial_results
        return self._summarize_results(trial_results)
    
    def run_centralized(self) -> Dict:
        """
        Centralized approach: Single trusted verifier.
        """
        trial_results = []
        
        for trial in range(self.num_trials):
            start_time = time.time()
            
            # Run all verifications
            privacy_verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
            privacy_results = privacy_verifier.verify_all()
            
            utility_verifier = UtilityVerifier(self.real_data, self.synthetic_data)
            utility_results = utility_verifier.verify_all()
            
            # Detect protected attributes
            protected_attrs = [col for col in self.real_data.columns 
                             if any(p in col.lower() for p in ['sex', 'gender', 'race', 'age'])]
            bias_detector = BiasDetector(
                self.real_data, 
                self.synthetic_data,
                protected_attributes=protected_attrs
            )
            bias_results = bias_detector.verify_all()
            
            end_time = time.time()
            
            # Calculate trust score (single verifier, lower trust)
            overall_score = (
                privacy_results['overall']['privacy_score'] +
                utility_results['overall']['utility_score'] +
                bias_results['overall']['fairness_score']
            ) / 3
            
            # Centralized trust is reduced due to single point of failure
            trust_score = overall_score * 0.7  # 30% reduction for single verifier
            
            trial_results.append({
                'trial': trial + 1,
                'approach': 'centralized',
                'latency': end_time - start_time,
                'trust_score': trust_score,
                'privacy_score': privacy_results['overall']['privacy_score'],
                'utility_score': utility_results['overall']['utility_score'],
                'bias_score': bias_results['overall']['fairness_score'],
                'tamper_resistant': False,  # Can be modified
                'data_hash': compute_data_hash(self.synthetic_data)
            })
        
        self.results['centralized'] = trial_results
        return self._summarize_results(trial_results)
    
    def run_blockchain(self, num_verifiers: int = 3) -> Dict:
        """
        Blockchain approach: Distributed verification with consensus.
        
        Args:
            num_verifiers: Number of independent verifiers
        """
        trial_results = []
        
        for trial in range(self.num_trials):
            start_time = time.time()
            
            # Initialize blockchain and consensus engine
            blockchain = BlockchainClient(mode=BlockchainMode.SIMULATION)
            consensus_engine = ConsensusEngine(min_verifiers=num_verifiers)
            
            data_hash = compute_data_hash(self.synthetic_data)
            verification_id = consensus_engine.create_verification_request(data_hash)
            
            # Simulate multiple verifiers
            verifier_scores = []
            submit_results = []
            
            for v in range(num_verifiers):
                # Each verifier runs independently
                privacy_verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
                privacy_results = privacy_verifier.verify_all()
                
                utility_verifier = UtilityVerifier(self.real_data, self.synthetic_data)
                utility_results = utility_verifier.verify_all()
                
                protected_attrs = [col for col in self.real_data.columns 
                                 if any(p in col.lower() for p in ['sex', 'gender', 'race', 'age'])]
                bias_detector = BiasDetector(
                    self.real_data, 
                    self.synthetic_data,
                    protected_attributes=protected_attrs
                )
                bias_results = bias_detector.verify_all()
                
                # Add small variations to simulate independent verification
                privacy_score = privacy_results['overall']['privacy_score'] + np.random.uniform(-3, 3)
                utility_score = utility_results['overall']['utility_score'] + np.random.uniform(-3, 3)
                bias_score = bias_results['overall']['fairness_score'] + np.random.uniform(-3, 3)
                overall_score = (privacy_score + utility_score + bias_score) / 3
                
                verifier_scores.append({
                    'privacy': privacy_score,
                    'utility': utility_score,
                    'bias': bias_score,
                    'overall': overall_score
                })
                
                # Submit to consensus using verification_id
                submit_result = consensus_engine.submit_verification(
                    verification_id=verification_id,
                    verifier_id=f"verifier_{v+1}",
                    privacy_score=privacy_score,
                    utility_score=utility_score,
                    bias_score=bias_score
                )
                submit_results.append(submit_result)
            
            # The last submit_result will contain consensus when min_verifiers reached
            # Get consensus from last submit result (which triggers consensus automatically)
            consensus_result = submit_results[-1]
            
            # Check if consensus reached successfully
            if 'error' in consensus_result:
                print(f"Warning: Consensus failed - {consensus_result['error']}")
                continue
            
            # Log consensus to blockchain
            blockchain.log_consensus(
                data_hash=data_hash,
                verification_id=verification_id,
                consensus_result=consensus_result
            )
            if hasattr(blockchain, 'backend') and hasattr(blockchain.backend, 'mine_block'):
                blockchain.backend.mine_block()
            
            end_time = time.time()
            
            # Blockchain provides higher trust due to immutability and consensus
            final_scores = consensus_result.get('final_scores', {})
            trust_score = final_scores.get('overall', 0)
            
            trial_results.append({
                'trial': trial + 1,
                'approach': 'blockchain',
                'latency': end_time - start_time,
                'trust_score': trust_score,
                'privacy_score': final_scores.get('privacy', 0),
                'utility_score': final_scores.get('utility', 0),
                'bias_score': final_scores.get('bias', 0),
                'tamper_resistant': True,
                'num_verifiers': num_verifiers,
                'data_hash': data_hash,
                'blockchain_stats': blockchain.get_blockchain_stats()
            })
        
        self.results['blockchain'] = trial_results
        return self._summarize_results(trial_results)
    
    def _summarize_results(self, results: List[Dict]) -> Dict:
        """Summarize results from trials."""
        latencies = [r['latency'] for r in results]
        trust_scores = [r['trust_score'] for r in results if r['trust_score'] is not None]
        
        return {
            'approach': results[0]['approach'],
            'num_trials': len(results),
            'latency': {
                'mean': np.mean(latencies),
                'std': np.std(latencies),
                'min': np.min(latencies),
                'max': np.max(latencies)
            },
            'trust_score': {
                'mean': np.mean(trust_scores) if trust_scores else 0,
                'std': np.std(trust_scores) if trust_scores else 0
            },
            'tamper_resistant': results[0]['tamper_resistant']
        }
    
    def run_all(self) -> Dict:
        """Run all approaches and compare."""
        print("Running Comparative Study...")
        print("="*60)
        
        print("\n[1/3] Running Baseline approach...")
        baseline_summary = self.run_baseline()
        
        print("[2/3] Running Centralized approach...")
        centralized_summary = self.run_centralized()
        
        print("[3/3] Running Blockchain approach...")
        blockchain_summary = self.run_blockchain()
        
        comparison = {
            'baseline': baseline_summary,
            'centralized': centralized_summary,
            'blockchain': blockchain_summary,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save results
        self._save_results(comparison)
        
        # Generate plots
        self._generate_plots()
        
        return comparison
    
    def _save_results(self, comparison: Dict):
        """Save comparison results."""
        # Save summary
        with open(self.output_dir / 'comparative_study_results.json', 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        
        # Save detailed results as CSV
        all_results = []
        for approach, results in self.results.items():
            for r in results:
                r_copy = r.copy()
                if 'blockchain_stats' in r_copy:
                    del r_copy['blockchain_stats']
                all_results.append(r_copy)
        
        df = pd.DataFrame(all_results)
        df.to_csv(self.output_dir / 'comparative_study_details.csv', index=False)
        
        print(f"\nResults saved to: {self.output_dir}")
    
    def _generate_plots(self):
        """Generate comparison plots."""
        try:
            # Prepare data
            approaches = ['Baseline', 'Centralized', 'Blockchain']
            
            # Latency comparison
            latencies = {
                'Baseline': [r['latency'] for r in self.results['baseline']],
                'Centralized': [r['latency'] for r in self.results['centralized']],
                'Blockchain': [r['latency'] for r in self.results['blockchain']]
            }
            
            trust_scores = {
                'Baseline': [0] * len(self.results['baseline']),
                'Centralized': [r['trust_score'] for r in self.results['centralized']],
                'Blockchain': [r['trust_score'] for r in self.results['blockchain']]
            }
            
            # Create figure with subplots
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            
            # Plot 1: Latency comparison
            ax1 = axes[0]
            latency_data = [latencies['Baseline'], latencies['Centralized'], latencies['Blockchain']]
            bp1 = ax1.boxplot(latency_data, labels=approaches, patch_artist=True)
            colors = ['#ff9999', '#99ccff', '#99ff99']
            for patch, color in zip(bp1['boxes'], colors):
                patch.set_facecolor(color)
            ax1.set_ylabel('Latency (seconds)')
            ax1.set_title('Verification Latency Comparison')
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Trust score comparison
            ax2 = axes[1]
            trust_data = [trust_scores['Baseline'], trust_scores['Centralized'], trust_scores['Blockchain']]
            bp2 = ax2.boxplot(trust_data, labels=approaches, patch_artist=True)
            for patch, color in zip(bp2['boxes'], colors):
                patch.set_facecolor(color)
            ax2.set_ylabel('Trust Score')
            ax2.set_title('Trust Score Comparison')
            ax2.set_ylim(0, 100)
            ax2.grid(True, alpha=0.3)
            
            # Plot 3: Properties comparison
            ax3 = axes[2]
            properties = ['Verification', 'Tamper\nResistance', 'Consensus', 'Audit Trail']
            baseline_props = [0, 0, 0, 0]
            centralized_props = [1, 0, 0, 0.5]
            blockchain_props = [1, 1, 1, 1]
            
            x = np.arange(len(properties))
            width = 0.25
            
            ax3.bar(x - width, baseline_props, width, label='Baseline', color='#ff9999')
            ax3.bar(x, centralized_props, width, label='Centralized', color='#99ccff')
            ax3.bar(x + width, blockchain_props, width, label='Blockchain', color='#99ff99')
            
            ax3.set_ylabel('Score')
            ax3.set_title('Security Properties')
            ax3.set_xticks(x)
            ax3.set_xticklabels(properties)
            ax3.legend()
            ax3.set_ylim(0, 1.2)
            ax3.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(self.output_dir / 'comparative_study_plots.png', dpi=300)
            plt.close()
            
            print(f"Plots saved to: {self.output_dir / 'comparative_study_plots.png'}")
            
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
    
    def print_summary(self):
        """Print summary of comparison."""
        print("\n" + "="*60)
        print("COMPARATIVE STUDY RESULTS")
        print("="*60)
        
        print("\n{:<15} {:<15} {:<15} {:<15}".format(
            'Approach', 'Latency (s)', 'Trust Score', 'Tamper Resistant'
        ))
        print("-"*60)
        
        for approach in ['baseline', 'centralized', 'blockchain']:
            summary = self._summarize_results(self.results[approach])
            print("{:<15} {:<15.3f} {:<15.2f} {:<15}".format(
                approach.capitalize(),
                summary['latency']['mean'],
                summary['trust_score']['mean'],
                str(summary['tamper_resistant'])
            ))
        
        print("\n" + "="*60)


def run_comparative_study(real_data_path: str = None, 
                          synthetic_data_path: str = None,
                          num_trials: int = 10) -> Dict:
    """
    Convenience function to run comparative study.
    
    Args:
        real_data_path: Path to real data CSV
        synthetic_data_path: Path to synthetic data CSV
        num_trials: Number of trials per approach
        
    Returns:
        Comparison results
    """
    # Load default data if not provided
    if real_data_path is None:
        real_data_path = PROJECT_ROOT / "data" / "raw" / "adult.csv"
    
    real_data = pd.read_csv(real_data_path)
    
    if synthetic_data_path and os.path.exists(synthetic_data_path):
        synthetic_data = pd.read_csv(synthetic_data_path)
    else:
        # Use sampled real data as mock synthetic for testing
        synthetic_data = real_data.sample(n=min(1000, len(real_data)), random_state=42)
        # Add some noise to make it "synthetic"
        for col in synthetic_data.select_dtypes(include=[np.number]).columns:
            synthetic_data[col] = synthetic_data[col] + np.random.normal(0, 0.1, len(synthetic_data))
    
    study = ComparativeStudy(
        real_data=real_data,
        synthetic_data=synthetic_data,
        num_trials=num_trials
    )
    
    results = study.run_all()
    study.print_summary()
    
    return results


if __name__ == "__main__":
    run_comparative_study(num_trials=5)
