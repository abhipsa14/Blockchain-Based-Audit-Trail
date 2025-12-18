"""
Fairness Post-Processor Module
Post-processing techniques to improve fairness in synthetic data.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings('ignore')


class FairnessPostProcessor:
    """
    Post-processing module to improve fairness metrics in synthetic data.
    
    Techniques:
    1. Rebalancing: Adjust group proportions to match real data
    2. Resampling: Oversample/undersample to achieve demographic parity
    3. Label flipping: Adjust outcomes to reduce disparate impact
    """
    
    def __init__(self, 
                 real_data: pd.DataFrame,
                 synthetic_data: pd.DataFrame,
                 protected_attributes: List[str],
                 target_column: Optional[str] = None):
        """
        Initialize the fairness post-processor.
        
        Args:
            real_data: Original dataset
            synthetic_data: Generated synthetic dataset
            protected_attributes: Columns representing protected groups
            target_column: Column representing the outcome/decision
        """
        self.real_data = real_data.copy()
        self.synthetic_data = synthetic_data.copy()
        self.protected_attributes = [pa for pa in protected_attributes 
                                     if pa in real_data.columns]
        self.target_column = target_column
        
    def rebalance_groups(self) -> pd.DataFrame:
        """
        Rebalance protected group proportions to match real data.
        
        Returns:
            Rebalanced synthetic data
        """
        result = self.synthetic_data.copy()
        
        for attr in self.protected_attributes:
            if attr not in result.columns:
                continue
                
            # Get real data distribution
            real_dist = self.real_data[attr].value_counts(normalize=True)
            
            # Calculate current synthetic distribution
            synth_dist = result[attr].value_counts(normalize=True)
            
            # Find groups that need adjustment
            resampled_dfs = []
            
            for group in real_dist.index:
                if group not in synth_dist.index:
                    continue
                    
                target_prop = real_dist[group]
                current_prop = synth_dist.get(group, 0)
                
                group_data = result[result[attr] == group]
                target_count = int(len(result) * target_prop)
                
                if len(group_data) > 0:
                    # Resample to target count
                    if len(group_data) >= target_count:
                        resampled = group_data.sample(n=target_count, replace=False)
                    else:
                        resampled = group_data.sample(n=target_count, replace=True)
                    resampled_dfs.append(resampled)
            
            if resampled_dfs:
                result = pd.concat(resampled_dfs, ignore_index=True)
        
        return result
    
    def reduce_disparate_impact(self, 
                                 favorable_outcome: Optional[str] = None,
                                 target_ratio: float = 0.9) -> pd.DataFrame:
        """
        Reduce disparate impact by adjusting outcome distributions.
        
        Args:
            favorable_outcome: Value representing favorable outcome
            target_ratio: Target disparate impact ratio (0.8-1.0 is fair)
            
        Returns:
            Adjusted synthetic data
        """
        if self.target_column is None or self.target_column not in self.synthetic_data.columns:
            return self.synthetic_data
            
        result = self.synthetic_data.copy()
        
        # Auto-detect favorable outcome if not provided
        if favorable_outcome is None:
            if result[self.target_column].dtype in ['int64', 'float64']:
                favorable_outcome = 1
            else:
                favorable_outcome = result[self.target_column].mode()[0]
        
        for attr in self.protected_attributes:
            if attr not in result.columns:
                continue
                
            groups = result[attr].unique()
            if len(groups) < 2:
                continue
            
            # Calculate favorable outcome rates per group
            group_rates = {}
            for group in groups:
                group_data = result[result[attr] == group]
                rate = (group_data[self.target_column] == favorable_outcome).mean()
                group_rates[group] = rate
            
            # Find privileged group (highest rate)
            privileged_group = max(group_rates, key=group_rates.get)
            privileged_rate = group_rates[privileged_group]
            
            if privileged_rate == 0:
                continue
            
            # Adjust unprivileged groups to reduce disparate impact
            for group in groups:
                if group == privileged_group:
                    continue
                    
                current_rate = group_rates[group]
                current_ratio = current_rate / privileged_rate if privileged_rate > 0 else 0
                
                if current_ratio < 0.8:  # Below fair threshold
                    # Need to increase favorable outcomes for this group
                    group_mask = result[attr] == group
                    unfavorable_mask = group_mask & (result[self.target_column] != favorable_outcome)
                    
                    # Calculate how many to flip
                    target_rate = privileged_rate * target_ratio
                    current_favorable = (result[group_mask][self.target_column] == favorable_outcome).sum()
                    group_size = group_mask.sum()
                    needed_favorable = int(group_size * target_rate)
                    to_flip = max(0, needed_favorable - current_favorable)
                    
                    # Randomly flip some unfavorable to favorable
                    unfavorable_indices = result[unfavorable_mask].index.tolist()
                    if to_flip > 0 and len(unfavorable_indices) > 0:
                        flip_indices = np.random.choice(
                            unfavorable_indices, 
                            size=min(to_flip, len(unfavorable_indices)),
                            replace=False
                        )
                        result.loc[flip_indices, self.target_column] = favorable_outcome
        
        return result
    
    def enforce_statistical_parity(self, 
                                    tolerance: float = 0.05) -> pd.DataFrame:
        """
        Enforce statistical parity across protected groups.
        
        Args:
            tolerance: Maximum allowed difference in group proportions
            
        Returns:
            Adjusted synthetic data
        """
        result = self.synthetic_data.copy()
        
        for attr in self.protected_attributes:
            if attr not in result.columns:
                continue
            
            real_dist = self.real_data[attr].value_counts(normalize=True)
            synth_dist = result[attr].value_counts(normalize=True)
            
            # Check if adjustment needed
            needs_adjustment = False
            for group in real_dist.index:
                if group in synth_dist.index:
                    diff = abs(real_dist[group] - synth_dist.get(group, 0))
                    if diff > tolerance:
                        needs_adjustment = True
                        break
            
            if needs_adjustment:
                # Resample to match real distribution
                resampled_dfs = []
                n_total = len(result)
                
                for group in real_dist.index:
                    group_data = result[result[attr] == group]
                    target_n = int(n_total * real_dist[group])
                    
                    if len(group_data) > 0 and target_n > 0:
                        if len(group_data) >= target_n:
                            resampled = group_data.sample(n=target_n, replace=False)
                        else:
                            resampled = group_data.sample(n=target_n, replace=True)
                        resampled_dfs.append(resampled)
                
                if resampled_dfs:
                    result = pd.concat(resampled_dfs, ignore_index=True)
        
        return result
    
    def apply_all(self, 
                  favorable_outcome: Optional[str] = None) -> pd.DataFrame:
        """
        Apply all fairness post-processing techniques.
        
        Args:
            favorable_outcome: Value representing favorable outcome
            
        Returns:
            Fairness-enhanced synthetic data
        """
        # Step 1: Rebalance group proportions
        result = self.rebalance_groups()
        
        # Update for subsequent steps
        self.synthetic_data = result
        
        # Step 2: Enforce statistical parity
        result = self.enforce_statistical_parity()
        self.synthetic_data = result
        
        # Step 3: Reduce disparate impact (if target column exists)
        if self.target_column is not None:
            result = self.reduce_disparate_impact(favorable_outcome)
        
        return result
    
    def get_improvement_report(self, 
                                original: pd.DataFrame,
                                processed: pd.DataFrame) -> Dict:
        """
        Generate report showing fairness improvements.
        
        Args:
            original: Original synthetic data
            processed: Post-processed synthetic data
            
        Returns:
            Improvement metrics
        """
        report = {
            'protected_attributes': self.protected_attributes,
            'improvements': {}
        }
        
        for attr in self.protected_attributes:
            if attr not in original.columns:
                continue
            
            real_dist = self.real_data[attr].value_counts(normalize=True)
            orig_dist = original[attr].value_counts(normalize=True)
            proc_dist = processed[attr].value_counts(normalize=True)
            
            attr_report = {
                'groups': {},
                'original_max_diff': 0,
                'processed_max_diff': 0
            }
            
            for group in real_dist.index:
                real_prop = real_dist.get(group, 0)
                orig_prop = orig_dist.get(group, 0)
                proc_prop = proc_dist.get(group, 0)
                
                orig_diff = abs(real_prop - orig_prop)
                proc_diff = abs(real_prop - proc_prop)
                
                attr_report['groups'][str(group)] = {
                    'real': float(real_prop),
                    'original': float(orig_prop),
                    'processed': float(proc_prop),
                    'original_diff': float(orig_diff),
                    'processed_diff': float(proc_diff),
                    'improved': proc_diff < orig_diff
                }
                
                attr_report['original_max_diff'] = max(attr_report['original_max_diff'], orig_diff)
                attr_report['processed_max_diff'] = max(attr_report['processed_max_diff'], proc_diff)
            
            attr_report['improvement'] = attr_report['original_max_diff'] - attr_report['processed_max_diff']
            report['improvements'][attr] = attr_report
        
        return report


def post_process_for_fairness(real_data: pd.DataFrame,
                               synthetic_data: pd.DataFrame,
                               protected_attributes: List[str],
                               target_column: Optional[str] = None,
                               favorable_outcome: Optional[str] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Convenience function for fairness post-processing.
    
    Args:
        real_data: Original dataset
        synthetic_data: Generated synthetic dataset
        protected_attributes: List of protected attribute columns
        target_column: Optional target column
        favorable_outcome: Value representing favorable outcome
        
    Returns:
        Tuple of (processed_data, improvement_report)
    """
    processor = FairnessPostProcessor(
        real_data=real_data,
        synthetic_data=synthetic_data,
        protected_attributes=protected_attributes,
        target_column=target_column
    )
    
    original = synthetic_data.copy()
    processed = processor.apply_all(favorable_outcome)
    report = processor.get_improvement_report(original, processed)
    
    return processed, report


if __name__ == "__main__":
    # Test with sample data
    print("Testing FairnessPostProcessor...")
    
    # Create sample data with bias
    np.random.seed(42)
    n = 1000
    
    real_data = pd.DataFrame({
        'age': np.random.randint(18, 80, n),
        'sex': np.random.choice(['Male', 'Female'], n, p=[0.5, 0.5]),
        'income': np.random.choice(['>50K', '<=50K'], n, p=[0.3, 0.7])
    })
    
    # Synthetic data with bias (more males, skewed income)
    synthetic_data = pd.DataFrame({
        'age': np.random.randint(18, 80, n),
        'sex': np.random.choice(['Male', 'Female'], n, p=[0.7, 0.3]),  # Biased
        'income': np.random.choice(['>50K', '<=50K'], n, p=[0.4, 0.6])
    })
    
    print("\nOriginal distributions:")
    print("Real sex:", real_data['sex'].value_counts(normalize=True).to_dict())
    print("Synth sex:", synthetic_data['sex'].value_counts(normalize=True).to_dict())
    
    # Apply fairness post-processing
    processed, report = post_process_for_fairness(
        real_data=real_data,
        synthetic_data=synthetic_data,
        protected_attributes=['sex'],
        target_column='income'
    )
    
    print("\nProcessed distributions:")
    print("Processed sex:", processed['sex'].value_counts(normalize=True).to_dict())
    
    print("\nImprovement Report:")
    for attr, data in report['improvements'].items():
        print(f"  {attr}: improvement = {data['improvement']:.4f}")
