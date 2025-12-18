"""
Utility Verification Module
Implements utility metrics for synthetic data validation:
- Statistical Similarity (Wasserstein Distance)
- Correlation Preservation
- ML Efficacy Test
"""

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance, ks_2samp
from scipy.spatial.distance import jensenshannon
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, f1_score, r2_score, mean_squared_error
from typing import Dict, List, Optional, Tuple, Union
import hashlib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class UtilityVerifier:
    """
    Verifies utility properties of synthetic data.
    
    Utility Score Formula:
    Utility Score = 0.4 * statistical_similarity_score +
                    0.3 * correlation_preservation_score +
                    0.3 * ml_efficacy_score
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                 categorical_columns: Optional[List[str]] = None,
                 target_column: Optional[str] = None):
        """
        Initialize the Utility Verifier.
        
        Args:
            real_data: Original dataset
            synthetic_data: Generated synthetic dataset
            categorical_columns: List of categorical column names
            target_column: Target column for ML efficacy test
        """
        self.real_data = real_data.copy()
        self.synthetic_data = synthetic_data.copy()
        self.categorical_columns = categorical_columns or self._detect_categorical()
        # Only include columns that are actually numeric (int or float dtypes)
        self.numerical_columns = [col for col in real_data.columns 
                                  if col not in self.categorical_columns
                                  and pd.api.types.is_numeric_dtype(real_data[col])]
        self.target_column = target_column
        
        # Results storage
        self.results = {}
        
    def _detect_categorical(self) -> List[str]:
        """Automatically detect categorical columns."""
        categorical = []
        for col in self.real_data.columns:
            if (self.real_data[col].dtype == 'object' or 
                self.real_data[col].dtype.name == 'category' or
                self.real_data[col].nunique() < 20):
                categorical.append(col)
        return categorical
    
    def compute_statistical_similarity(self) -> Dict:
        """
        Compute statistical similarity using multiple metrics.
        
        Metrics:
        - Wasserstein Distance for numerical columns
        - Jensen-Shannon Divergence for categorical columns
        - KS Test for distribution comparison
        
        Returns:
            Dictionary with statistical similarity metrics
        """
        wasserstein_distances = {}
        js_divergences = {}
        ks_statistics = {}
        
        # Numerical columns - Wasserstein Distance
        for col in self.numerical_columns:
            if col in self.real_data.columns and col in self.synthetic_data.columns:
                try:
                    # Ensure numeric type and drop NaNs
                    real_vals = pd.to_numeric(self.real_data[col], errors='coerce').dropna().values.astype(float)
                    synth_vals = pd.to_numeric(self.synthetic_data[col], errors='coerce').dropna().values.astype(float)
                    
                    if len(real_vals) == 0 or len(synth_vals) == 0:
                        continue
                    
                    # Normalize for fair comparison
                    real_std = real_vals.std()
                    if real_std == 0:
                        real_std = 1e-10
                    real_normalized = (real_vals - real_vals.mean()) / (real_std + 1e-10)
                    synth_normalized = (synth_vals - real_vals.mean()) / (real_std + 1e-10)
                    
                    # Wasserstein distance
                    wd = wasserstein_distance(real_normalized, synth_normalized)
                    wasserstein_distances[col] = float(wd)
                    
                    # KS test
                    ks_stat, ks_pval = ks_2samp(real_vals, synth_vals)
                    ks_statistics[col] = {'statistic': float(ks_stat), 'p_value': float(ks_pval)}
                except Exception as e:
                    # Skip columns that can't be processed
                    continue
        
        # Categorical columns - Jensen-Shannon Divergence
        for col in self.categorical_columns:
            if col in self.real_data.columns and col in self.synthetic_data.columns:
                try:
                    real_dist = self.real_data[col].value_counts(normalize=True)
                    synth_dist = self.synthetic_data[col].value_counts(normalize=True)
                    
                    # Convert to dict for proper .get() access
                    real_dist_dict = real_dist.to_dict()
                    synth_dist_dict = synth_dist.to_dict()
                    
                    # Align distributions
                    all_values = sorted(set(real_dist_dict.keys()) | set(synth_dist_dict.keys()))
                    real_aligned = np.array([real_dist_dict.get(v, 0) for v in all_values])
                    synth_aligned = np.array([synth_dist_dict.get(v, 0) for v in all_values])
                    
                    # Add small epsilon to avoid division by zero
                    real_aligned = real_aligned + 1e-10
                    synth_aligned = synth_aligned + 1e-10
                    
                    # Normalize
                    real_aligned = real_aligned / real_aligned.sum()
                    synth_aligned = synth_aligned / synth_aligned.sum()
                    
                    js_div = jensenshannon(real_aligned, synth_aligned)
                    js_divergences[col] = float(js_div)
                except Exception as e:
                    # Skip columns that can't be processed
                    continue
        
        # Calculate scores
        avg_wd = np.mean(list(wasserstein_distances.values())) if wasserstein_distances else 0
        avg_js = np.mean(list(js_divergences.values())) if js_divergences else 0
        
        # Score: Lower distance is better
        # Threshold: WD < 0.1, JS < 0.1 is excellent
        wd_score = max(0, 100 - avg_wd * 500) if avg_wd < 0.2 else 0
        js_score = max(0, 100 - avg_js * 500) if avg_js < 0.2 else 0
        
        combined_score = (wd_score * 0.6 + js_score * 0.4) if js_divergences else wd_score
        
        self.results['statistical_similarity'] = {
            'wasserstein_distances': wasserstein_distances,
            'avg_wasserstein': avg_wd,
            'js_divergences': js_divergences,
            'avg_js_divergence': avg_js,
            'ks_statistics': ks_statistics,
            'score': combined_score,
            'passed': avg_wd < 0.1 and avg_js < 0.15
        }
        
        return self.results['statistical_similarity']
    
    def compute_correlation_preservation(self) -> Dict:
        """
        Measure how well correlations are preserved.
        
        Compares correlation matrices between real and synthetic data.
        
        Returns:
            Dictionary with correlation preservation metrics
        """
        # Encode categorical columns for correlation
        real_encoded = self._encode_for_correlation(self.real_data)
        synth_encoded = self._encode_for_correlation(self.synthetic_data)
        
        # Compute correlation matrices
        real_corr = real_encoded.corr()
        synth_corr = synth_encoded.corr()
        
        # Align columns
        common_cols = list(set(real_corr.columns) & set(synth_corr.columns))
        real_corr = real_corr.loc[common_cols, common_cols]
        synth_corr = synth_corr.loc[common_cols, common_cols]
        
        # Mean absolute difference
        corr_diff = np.abs(real_corr.values - synth_corr.values)
        mean_diff = float(np.mean(corr_diff))
        max_diff = float(np.max(corr_diff))
        
        # Per-column correlation preservation
        column_diffs = {}
        for col in common_cols:
            col_diff = float(np.mean(np.abs(real_corr[col] - synth_corr[col])))
            column_diffs[col] = col_diff
        
        # Score: Lower difference is better
        # Threshold: Mean diff < 0.1 is excellent
        score = max(0, 100 - mean_diff * 500)
        
        self.results['correlation_preservation'] = {
            'mean_correlation_diff': mean_diff,
            'max_correlation_diff': max_diff,
            'column_differences': column_diffs,
            'real_correlation_matrix': real_corr.to_dict(),
            'synthetic_correlation_matrix': synth_corr.to_dict(),
            'score': score,
            'passed': mean_diff < 0.1
        }
        
        return self.results['correlation_preservation']
    
    def _encode_for_correlation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode categorical columns for correlation computation."""
        df_encoded = df.copy()
        
        for col in self.categorical_columns:
            if col in df_encoded.columns:
                le = LabelEncoder()
                df_encoded[col] = le.fit_transform(df_encoded[col].astype(str))
        
        return df_encoded
    
    def ml_efficacy_test(self, target_column: Optional[str] = None,
                         test_size: float = 0.3) -> Dict:
        """
        Test ML efficacy: Train on synthetic, test on real.
        
        Compares model performance when trained on synthetic vs real data.
        
        Args:
            target_column: Column to predict
            test_size: Fraction of real data to use for testing
            
        Returns:
            Dictionary with ML efficacy metrics
        """
        target = target_column or self.target_column
        
        if target is None:
            # Try to auto-detect target (last column or binary column)
            for col in reversed(self.real_data.columns):
                if self.real_data[col].nunique() <= 10:
                    target = col
                    break
        
        if target is None or target not in self.real_data.columns:
            return {'error': 'No valid target column specified or detected'}
        
        # Determine task type
        is_classification = (self.real_data[target].nunique() <= 10 or 
                            self.real_data[target].dtype == 'object')
        
        # Prepare data
        feature_cols = [col for col in self.real_data.columns if col != target]
        
        # Encode features
        real_X = self._encode_features(self.real_data[feature_cols])
        synth_X = self._encode_features(self.synthetic_data[feature_cols])
        
        # Encode target
        if is_classification:
            le = LabelEncoder()
            real_y = le.fit_transform(self.real_data[target].astype(str))
            synth_y = le.transform(self.synthetic_data[target].astype(str))
        else:
            real_y = self.real_data[target].values
            synth_y = self.synthetic_data[target].values
        
        # Split real data for testing
        real_X_train, real_X_test, real_y_train, real_y_test = train_test_split(
            real_X, real_y, test_size=test_size, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        real_X_train_scaled = scaler.fit_transform(real_X_train)
        real_X_test_scaled = scaler.transform(real_X_test)
        synth_X_scaled = scaler.transform(synth_X)
        
        results = {}
        
        if is_classification:
            # Train on real, test on real (baseline)
            clf_real = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            clf_real.fit(real_X_train_scaled, real_y_train)
            baseline_acc = accuracy_score(real_y_test, clf_real.predict(real_X_test_scaled))
            baseline_f1 = f1_score(real_y_test, clf_real.predict(real_X_test_scaled), average='weighted')
            
            # Train on synthetic, test on real
            clf_synth = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            clf_synth.fit(synth_X_scaled, synth_y)
            synth_acc = accuracy_score(real_y_test, clf_synth.predict(real_X_test_scaled))
            synth_f1 = f1_score(real_y_test, clf_synth.predict(real_X_test_scaled), average='weighted')
            
            results = {
                'task_type': 'classification',
                'baseline_accuracy': float(baseline_acc),
                'baseline_f1': float(baseline_f1),
                'synthetic_accuracy': float(synth_acc),
                'synthetic_f1': float(synth_f1),
                'accuracy_ratio': float(synth_acc / baseline_acc) if baseline_acc > 0 else 0,
                'f1_ratio': float(synth_f1 / baseline_f1) if baseline_f1 > 0 else 0
            }
            
            # Score based on how close synthetic performance is to baseline
            efficacy_ratio = results['accuracy_ratio']
            
        else:
            # Regression task
            reg_real = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            reg_real.fit(real_X_train_scaled, real_y_train)
            baseline_r2 = r2_score(real_y_test, reg_real.predict(real_X_test_scaled))
            baseline_rmse = np.sqrt(mean_squared_error(real_y_test, reg_real.predict(real_X_test_scaled)))
            
            reg_synth = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            reg_synth.fit(synth_X_scaled, synth_y)
            synth_r2 = r2_score(real_y_test, reg_synth.predict(real_X_test_scaled))
            synth_rmse = np.sqrt(mean_squared_error(real_y_test, reg_synth.predict(real_X_test_scaled)))
            
            results = {
                'task_type': 'regression',
                'baseline_r2': float(baseline_r2),
                'baseline_rmse': float(baseline_rmse),
                'synthetic_r2': float(synth_r2),
                'synthetic_rmse': float(synth_rmse),
                'r2_ratio': float(synth_r2 / baseline_r2) if baseline_r2 > 0 else 0
            }
            
            efficacy_ratio = max(0, results['r2_ratio'])
        
        # Score: 70% of baseline performance is threshold
        score = min(100, efficacy_ratio * 100 / 0.7) if efficacy_ratio < 1 else 100
        
        results['score'] = score
        results['efficacy_ratio'] = efficacy_ratio
        results['passed'] = efficacy_ratio >= 0.7  # At least 70% of baseline
        results['target_column'] = target
        
        self.results['ml_efficacy'] = results
        
        return self.results['ml_efficacy']
    
    def _encode_features(self, df: pd.DataFrame) -> np.ndarray:
        """Encode features for ML models."""
        df_encoded = df.copy()
        
        for col in df.columns:
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                le = LabelEncoder()
                # Fit on combined unique values to handle unseen categories
                all_values = pd.concat([
                    self.real_data[col] if col in self.real_data.columns else pd.Series(),
                    self.synthetic_data[col] if col in self.synthetic_data.columns else pd.Series()
                ]).astype(str).unique()
                le.fit(all_values)
                df_encoded[col] = le.transform(df[col].astype(str))
            
            # Fill NaN values
            df_encoded[col] = df_encoded[col].fillna(df_encoded[col].median() if df_encoded[col].dtype in ['int64', 'float64'] else 0)
        
        return df_encoded.values
    
    def verify_all(self, target_column: Optional[str] = None) -> Dict:
        """
        Run all utility verification tests.
        
        Args:
            target_column: Optional target column for ML efficacy test
            
        Returns:
            Complete verification results with overall utility score
        """
        # Run all tests
        self.compute_statistical_similarity()
        self.compute_correlation_preservation()
        self.ml_efficacy_test(target_column)
        
        # Calculate weighted overall score
        weights = {
            'statistical_similarity': 0.4,
            'correlation_preservation': 0.3,
            'ml_efficacy': 0.3
        }
        
        overall_score = sum(
            self.results[key]['score'] * weight 
            for key, weight in weights.items()
            if key in self.results and 'score' in self.results[key]
        )
        
        # Overall pass/fail
        all_passed = all(
            self.results[key].get('passed', False) 
            for key in weights.keys() 
            if key in self.results
        )
        
        self.results['overall'] = {
            'utility_score': overall_score,
            'passed': all_passed,
            'threshold': 70,
            'weights': weights
        }
        
        return self.results
    
    def generate_report(self, target_column: Optional[str] = None) -> Dict:
        """Generate a comprehensive utility verification report."""
        if not self.results:
            self.verify_all(target_column)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'data_hash': self._compute_data_hash(),
            'real_data_shape': list(self.real_data.shape),
            'synthetic_data_shape': list(self.synthetic_data.shape),
            'verification_results': self.results,
            'summary': {
                'utility_score': self.results['overall']['utility_score'],
                'status': 'PASSED' if self.results['overall']['passed'] else 'FAILED',
                'recommendations': self._generate_recommendations()
            }
        }
        
        return report
    
    def _compute_data_hash(self) -> str:
        """Compute hash of the synthetic data."""
        data_string = self.synthetic_data.to_json()
        return hashlib.sha256(data_string.encode()).hexdigest()
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []
        
        if 'statistical_similarity' in self.results:
            if not self.results['statistical_similarity']['passed']:
                recommendations.append(
                    "Statistical distributions differ significantly. "
                    "Consider increasing training epochs or adjusting generator architecture."
                )
        
        if 'correlation_preservation' in self.results:
            if not self.results['correlation_preservation']['passed']:
                high_diff_cols = [
                    col for col, diff in self.results['correlation_preservation']['column_differences'].items()
                    if diff > 0.15
                ]
                if high_diff_cols:
                    recommendations.append(
                        f"Poor correlation preservation for columns: {', '.join(high_diff_cols[:3])}. "
                        "Consider using correlation-aware generators."
                    )
        
        if 'ml_efficacy' in self.results:
            if not self.results['ml_efficacy']['passed']:
                recommendations.append(
                    f"ML efficacy ratio is {self.results['ml_efficacy']['efficacy_ratio']:.2%}. "
                    "Synthetic data may not be suitable for downstream ML tasks."
                )
        
        if not recommendations:
            recommendations.append("All utility checks passed. Data maintains good utility.")
        
        return recommendations


# Convenience function
def verify_utility(real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                   categorical_columns: Optional[List[str]] = None,
                   target_column: Optional[str] = None) -> Dict:
    """
    Quick utility verification function.
    
    Args:
        real_data: Original dataset
        synthetic_data: Generated synthetic dataset
        categorical_columns: Optional list of categorical columns
        target_column: Optional target column for ML test
        
    Returns:
        Utility verification results
    """
    verifier = UtilityVerifier(real_data, synthetic_data, categorical_columns, target_column)
    return verifier.verify_all(target_column)
