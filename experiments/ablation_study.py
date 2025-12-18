"""
Ablation Study Module
Tests the contribution of each verification component.
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


class AblationStudy:
    """
    Ablation study to evaluate the contribution of each system component.
    
    Components tested:
    1. Privacy Verification (DCR, k-anonymity, MIA)
    2. Utility Verification (Wasserstein, correlation, ML efficacy)
    3. Bias Detection (demographic parity, disparate impact)
    4. Consensus Mechanism
    5. Blockchain Logging
    """
    
    def __init__(self,
                 real_data: pd.DataFrame,
                 synthetic_data: pd.DataFrame,
                 output_dir: str = "results/experiments"):
        """
        Initialize ablation study.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            output_dir: Directory for results
        """
        self.real_data = real_data
        self.synthetic_data = synthetic_data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {}
        
    def test_privacy_components(self, num_trials: int = 5) -> Dict:
        """
        Test contribution of each privacy metric.
        
        Components:
        - DCR (Distance to Closest Record)
        - k-Anonymity
        - Membership Inference Attack resistance
        - Attribute Disclosure Risk
        """
        print("\nTesting Privacy Component Contributions...")
        print("-"*50)
        
        results = {
            'full': [],
            'no_dcr': [],
            'no_kanon': [],
            'no_mia': [],
            'no_disclosure': []
        }
        
        for trial in range(num_trials):
            verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
            
            # Full verification
            start = time.time()
            full_results = verifier.verify_all()
            full_time = time.time() - start
            results['full'].append({
                'trial': trial + 1,
                'score': full_results['privacy_score'],
                'time': full_time
            })
            
            # Without DCR
            start = time.time()
            dcr_result = verifier.compute_dcr()
            no_dcr_score = self._recalculate_privacy_score(full_results, exclude='dcr')
            results['no_dcr'].append({
                'trial': trial + 1,
                'score': no_dcr_score,
                'time': full_time - (time.time() - start),
                'contribution': full_results['privacy_score'] - no_dcr_score
            })
            
            # Without k-anonymity
            no_kanon_score = self._recalculate_privacy_score(full_results, exclude='k_anonymity')
            results['no_kanon'].append({
                'trial': trial + 1,
                'score': no_kanon_score,
                'contribution': full_results['privacy_score'] - no_kanon_score
            })
            
            # Without MIA
            no_mia_score = self._recalculate_privacy_score(full_results, exclude='mia')
            results['no_mia'].append({
                'trial': trial + 1,
                'score': no_mia_score,
                'contribution': full_results['privacy_score'] - no_mia_score
            })
            
            # Without Attribute Disclosure
            no_disclosure_score = self._recalculate_privacy_score(full_results, exclude='disclosure')
            results['no_disclosure'].append({
                'trial': trial + 1,
                'score': no_disclosure_score,
                'contribution': full_results['privacy_score'] - no_disclosure_score
            })
        
        self.results['privacy'] = results
        return self._summarize_component_results(results)
    
    def _recalculate_privacy_score(self, full_results: Dict, exclude: str) -> float:
        """Recalculate privacy score excluding one component."""
        weights = {
            'dcr': 0.3,
            'k_anonymity': 0.2,
            'mia': 0.3,
            'disclosure': 0.2
        }
        
        scores = {
            'dcr': full_results.get('dcr', {}).get('score', 70),
            'k_anonymity': full_results.get('k_anonymity', {}).get('score', 70),
            'mia': full_results.get('membership_inference', {}).get('score', 70),
            'disclosure': full_results.get('attribute_disclosure', {}).get('score', 70)
        }
        
        # Exclude component and renormalize weights
        remaining_weights = {k: v for k, v in weights.items() if k != exclude}
        total_weight = sum(remaining_weights.values())
        
        score = sum(
            scores[k] * (v / total_weight) 
            for k, v in remaining_weights.items()
        )
        
        return score
    
    def test_utility_components(self, num_trials: int = 5) -> Dict:
        """
        Test contribution of each utility metric.
        
        Components:
        - Statistical Similarity (Wasserstein Distance)
        - Correlation Preservation
        - ML Efficacy
        """
        print("\nTesting Utility Component Contributions...")
        print("-"*50)
        
        results = {
            'full': [],
            'no_statistical': [],
            'no_correlation': [],
            'no_ml_efficacy': []
        }
        
        for trial in range(num_trials):
            verifier = UtilityVerifier(self.real_data, self.synthetic_data)
            
            # Full verification
            start = time.time()
            full_results = verifier.verify_all()
            full_time = time.time() - start
            
            results['full'].append({
                'trial': trial + 1,
                'score': full_results['utility_score'],
                'time': full_time
            })
            
            # Ablation tests
            for component, key in [
                ('statistical', 'no_statistical'),
                ('correlation', 'no_correlation'),
                ('ml_efficacy', 'no_ml_efficacy')
            ]:
                ablated_score = self._recalculate_utility_score(full_results, exclude=component)
                results[key].append({
                    'trial': trial + 1,
                    'score': ablated_score,
                    'contribution': full_results['utility_score'] - ablated_score
                })
        
        self.results['utility'] = results
        return self._summarize_component_results(results)
    
    def _recalculate_utility_score(self, full_results: Dict, exclude: str) -> float:
        """Recalculate utility score excluding one component."""
        weights = {
            'statistical': 0.4,
            'correlation': 0.3,
            'ml_efficacy': 0.3
        }
        
        scores = {
            'statistical': full_results.get('statistical_similarity', {}).get('score', 70),
            'correlation': full_results.get('correlation_preservation', {}).get('score', 70),
            'ml_efficacy': full_results.get('ml_efficacy', {}).get('score', 70)
        }
        
        remaining_weights = {k: v for k, v in weights.items() if k != exclude}
        total_weight = sum(remaining_weights.values())
        
        score = sum(
            scores[k] * (v / total_weight)
            for k, v in remaining_weights.items()
        )
        
        return score
    
    def test_consensus_impact(self, num_trials: int = 5) -> Dict:
        """
        Test impact of consensus mechanism.
        
        Compares:
        - Single verifier (no consensus)
        - 3 verifiers (minimum consensus)
        - 5 verifiers (recommended consensus)
        """
        print("\nTesting Consensus Mechanism Impact...")
        print("-"*50)
        
        results = {
            'single': [],
            'three_verifiers': [],
            'five_verifiers': []
        }
        
        data_hash = compute_data_hash(self.synthetic_data)
        
        for trial in range(num_trials):
            # Single verifier
            privacy_verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
            privacy_results = privacy_verifier.verify_all()
            
            utility_verifier = UtilityVerifier(self.real_data, self.synthetic_data)
            utility_results = utility_verifier.verify_all()
            
            single_score = (privacy_results['privacy_score'] + utility_results['utility_score']) / 2
            results['single'].append({
                'trial': trial + 1,
                'score': single_score,
                'variance': 0  # No variance with single verifier
            })
            
            # Multiple verifiers
            for num_verifiers, key in [(3, 'three_verifiers'), (5, 'five_verifiers')]:
                consensus_engine = ConsensusEngine(min_verifiers=num_verifiers)
                consensus_engine.create_verification_request(data_hash)
                
                verifier_scores = []
                for v in range(num_verifiers):
                    # Add variation
                    score = single_score + np.random.uniform(-5, 5)
                    score = max(0, min(100, score))
                    verifier_scores.append(score)
                    
                    consensus_engine.submit_verification(
                        data_hash=data_hash,
                        verifier_id=f"verifier_{v+1}",
                        privacy_score=privacy_results['privacy_score'] + np.random.uniform(-3, 3),
                        utility_score=utility_results['utility_score'] + np.random.uniform(-3, 3),
                        bias_score=80.0,
                        overall_score=score
                    )
                
                consensus_record = consensus_engine.get_consensus(data_hash)
                
                results[key].append({
                    'trial': trial + 1,
                    'score': consensus_record.final_overall_score,
                    'variance': np.var(verifier_scores),
                    'agreement_rate': self._calculate_agreement_rate(verifier_scores)
                })
        
        self.results['consensus'] = results
        return self._summarize_consensus_results(results)
    
    def _calculate_agreement_rate(self, scores: List[float], threshold: float = 5.0) -> float:
        """Calculate agreement rate among verifiers."""
        median = np.median(scores)
        agreements = sum(1 for s in scores if abs(s - median) <= threshold)
        return agreements / len(scores)
    
    def test_blockchain_overhead(self, num_trials: int = 5) -> Dict:
        """
        Test blockchain overhead.
        
        Compares verification time with and without blockchain logging.
        """
        print("\nTesting Blockchain Overhead...")
        print("-"*50)
        
        results = {
            'without_blockchain': [],
            'with_blockchain': []
        }
        
        for trial in range(num_trials):
            # Without blockchain
            start = time.time()
            privacy_verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
            privacy_results = privacy_verifier.verify_all()
            utility_verifier = UtilityVerifier(self.real_data, self.synthetic_data)
            utility_results = utility_verifier.verify_all()
            without_time = time.time() - start
            
            results['without_blockchain'].append({
                'trial': trial + 1,
                'time': without_time
            })
            
            # With blockchain
            start = time.time()
            blockchain = BlockchainClient(mode=BlockchainMode.SIMULATION)
            
            privacy_verifier = PrivacyVerifier(self.real_data, self.synthetic_data)
            privacy_results = privacy_verifier.verify_all()
            
            blockchain.log_verification(
                data_hash=compute_data_hash(self.synthetic_data),
                verifier_id="test",
                verification_type="privacy",
                results=privacy_results
            )
            
            utility_verifier = UtilityVerifier(self.real_data, self.synthetic_data)
            utility_results = utility_verifier.verify_all()
            
            blockchain.log_verification(
                data_hash=compute_data_hash(self.synthetic_data),
                verifier_id="test",
                verification_type="utility",
                results=utility_results
            )
            
            blockchain.mine_block()
            
            with_time = time.time() - start
            
            results['with_blockchain'].append({
                'trial': trial + 1,
                'time': with_time,
                'overhead': with_time - without_time,
                'overhead_percent': ((with_time - without_time) / without_time) * 100
            })
        
        self.results['blockchain'] = results
        return self._summarize_blockchain_results(results)
    
    def _summarize_component_results(self, results: Dict) -> Dict:
        """Summarize component ablation results."""
        summary = {}
        for key, trials in results.items():
            scores = [t['score'] for t in trials]
            summary[key] = {
                'mean_score': np.mean(scores),
                'std_score': np.std(scores)
            }
            if 'contribution' in trials[0]:
                contributions = [t['contribution'] for t in trials]
                summary[key]['mean_contribution'] = np.mean(contributions)
        return summary
    
    def _summarize_consensus_results(self, results: Dict) -> Dict:
        """Summarize consensus ablation results."""
        summary = {}
        for key, trials in results.items():
            scores = [t['score'] for t in trials]
            variances = [t.get('variance', 0) for t in trials]
            summary[key] = {
                'mean_score': np.mean(scores),
                'mean_variance': np.mean(variances)
            }
        return summary
    
    def _summarize_blockchain_results(self, results: Dict) -> Dict:
        """Summarize blockchain overhead results."""
        without_times = [t['time'] for t in results['without_blockchain']]
        with_times = [t['time'] for t in results['with_blockchain']]
        overheads = [t['overhead_percent'] for t in results['with_blockchain']]
        
        return {
            'without_blockchain_mean': np.mean(without_times),
            'with_blockchain_mean': np.mean(with_times),
            'mean_overhead_percent': np.mean(overheads)
        }
    
    def run_all(self) -> Dict:
        """Run all ablation tests."""
        print("\n" + "="*60)
        print("ABLATION STUDY")
        print("="*60)
        
        privacy_summary = self.test_privacy_components()
        utility_summary = self.test_utility_components()
        consensus_summary = self.test_consensus_impact()
        blockchain_summary = self.test_blockchain_overhead()
        
        # Save results
        self._save_results()
        
        # Generate plots
        self._generate_plots()
        
        return {
            'privacy': privacy_summary,
            'utility': utility_summary,
            'consensus': consensus_summary,
            'blockchain': blockchain_summary
        }
    
    def _save_results(self):
        """Save results to files."""
        with open(self.output_dir / 'ablation_study_results.json', 'w') as f:
            json.dump({
                'results': self.results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\nResults saved to: {self.output_dir}")
    
    def _generate_plots(self):
        """Generate ablation study plots."""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            
            # Plot 1: Privacy component contributions
            ax1 = axes[0, 0]
            if 'privacy' in self.results:
                components = ['DCR', 'k-Anonymity', 'MIA', 'Disclosure']
                contributions = []
                for key in ['no_dcr', 'no_kanon', 'no_mia', 'no_disclosure']:
                    trials = self.results['privacy'].get(key, [])
                    if trials and 'contribution' in trials[0]:
                        contributions.append(np.mean([t['contribution'] for t in trials]))
                    else:
                        contributions.append(0)
                
                colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(components)))
                ax1.bar(components, contributions, color=colors)
                ax1.set_ylabel('Score Contribution')
                ax1.set_title('Privacy Component Contributions')
                ax1.grid(True, alpha=0.3)
            
            # Plot 2: Utility component contributions
            ax2 = axes[0, 1]
            if 'utility' in self.results:
                components = ['Statistical', 'Correlation', 'ML Efficacy']
                contributions = []
                for key in ['no_statistical', 'no_correlation', 'no_ml_efficacy']:
                    trials = self.results['utility'].get(key, [])
                    if trials and 'contribution' in trials[0]:
                        contributions.append(np.mean([t['contribution'] for t in trials]))
                    else:
                        contributions.append(0)
                
                colors = plt.cm.Greens(np.linspace(0.4, 0.8, len(components)))
                ax2.bar(components, contributions, color=colors)
                ax2.set_ylabel('Score Contribution')
                ax2.set_title('Utility Component Contributions')
                ax2.grid(True, alpha=0.3)
            
            # Plot 3: Consensus impact
            ax3 = axes[1, 0]
            if 'consensus' in self.results:
                configs = ['Single', '3 Verifiers', '5 Verifiers']
                scores = []
                for key in ['single', 'three_verifiers', 'five_verifiers']:
                    trials = self.results['consensus'].get(key, [])
                    if trials:
                        scores.append(np.mean([t['score'] for t in trials]))
                    else:
                        scores.append(0)
                
                colors = plt.cm.Oranges(np.linspace(0.4, 0.8, len(configs)))
                ax3.bar(configs, scores, color=colors)
                ax3.set_ylabel('Final Score')
                ax3.set_title('Consensus Configuration Impact')
                ax3.set_ylim(0, 100)
                ax3.grid(True, alpha=0.3)
            
            # Plot 4: Blockchain overhead
            ax4 = axes[1, 1]
            if 'blockchain' in self.results:
                configs = ['Without\nBlockchain', 'With\nBlockchain']
                times = [
                    np.mean([t['time'] for t in self.results['blockchain']['without_blockchain']]),
                    np.mean([t['time'] for t in self.results['blockchain']['with_blockchain']])
                ]
                
                colors = ['#99ccff', '#ff9999']
                ax4.bar(configs, times, color=colors)
                ax4.set_ylabel('Time (seconds)')
                ax4.set_title('Blockchain Overhead')
                ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(self.output_dir / 'ablation_study_plots.png', dpi=300)
            plt.close()
            
            print(f"Plots saved to: {self.output_dir / 'ablation_study_plots.png'}")
            
        except Exception as e:
            print(f"Warning: Could not generate plots: {e}")
    
    def print_summary(self):
        """Print summary of ablation study."""
        print("\n" + "="*60)
        print("ABLATION STUDY RESULTS")
        print("="*60)
        
        if 'privacy' in self.results:
            print("\n--- Privacy Component Contributions ---")
            for key in ['no_dcr', 'no_kanon', 'no_mia', 'no_disclosure']:
                trials = self.results['privacy'].get(key, [])
                if trials and 'contribution' in trials[0]:
                    contribution = np.mean([t['contribution'] for t in trials])
                    print(f"{key}: {contribution:.2f} points")
        
        if 'blockchain' in self.results:
            print("\n--- Blockchain Overhead ---")
            overheads = [t['overhead_percent'] for t in self.results['blockchain']['with_blockchain']]
            print(f"Mean overhead: {np.mean(overheads):.2f}%")


def run_ablation_study(real_data_path: str = None, num_trials: int = 5) -> Dict:
    """
    Convenience function to run ablation study.
    
    Args:
        real_data_path: Path to data CSV
        num_trials: Number of trials per test
        
    Returns:
        Study results
    """
    if real_data_path is None:
        real_data_path = PROJECT_ROOT / "data" / "raw" / "adult.csv"
    
    real_data = pd.read_csv(real_data_path)
    
    # Create mock synthetic data
    synthetic_data = real_data.sample(n=min(1000, len(real_data)), random_state=42)
    for col in synthetic_data.select_dtypes(include=[np.number]).columns:
        synthetic_data[col] = synthetic_data[col] + np.random.normal(0, 0.1, len(synthetic_data))
    
    study = AblationStudy(real_data=real_data, synthetic_data=synthetic_data)
    results = study.run_all()
    study.print_summary()
    
    return results


if __name__ == "__main__":
    run_ablation_study(num_trials=3)
