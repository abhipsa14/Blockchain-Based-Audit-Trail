
        let currentUploadId = null;
        let currentRequestId = null;
        let currentPreprocessingReport = null;  // Store preprocessing report

        let generatedDataAvailable = false;
        
        // Mode toggle handler
        document.querySelectorAll('input[name="mode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                updateModeUI();
            });
        });
        
        function updateModeUI() {
            const mode = document.querySelector('input[name="mode"]:checked').value;
            const modeDescription = document.getElementById('modeDescription');
            const syntheticOptional = document.getElementById('syntheticOptional');
            const realRequired = document.getElementById('realRequired');
            const realZone = document.getElementById('realZone');
            const syntheticZone = document.getElementById('syntheticZone');
            const numRowsContainer = document.getElementById('numRowsContainer');
            
            if (mode === 'generate') {
                // Generate & Verify: Real required, Synthetic optional
                modeDescription.innerHTML = '<strong>Generate & Verify:</strong> Upload real data, system generates synthetic data and verifies it.';
                syntheticOptional.textContent = '(Optional - will be generated)';
                syntheticOptional.className = 'text-muted';
                realRequired.textContent = '*';
                realRequired.className = 'text-danger';
                realZone.style.opacity = '1';
                syntheticZone.style.opacity = '0.6';
                numRowsContainer.style.display = 'block';
            } else if (mode === 'upload') {
                // Upload Both: Both required
                modeDescription.innerHTML = '<strong>Upload Both:</strong> Upload both real and synthetic datasets for verification comparison.';
                syntheticOptional.textContent = '(Required)';
                syntheticOptional.className = 'text-danger';
                realRequired.textContent = '*';
                realRequired.className = 'text-danger';
                realZone.style.opacity = '1';
                syntheticZone.style.opacity = '1';
                numRowsContainer.style.display = 'none';
            } else if (mode === 'synthetic_only') {
                // Synthetic Only: Only synthetic required
                modeDescription.innerHTML = '<strong>Synthetic Only:</strong> Upload only synthetic data for quality analysis (no real data comparison).';
                syntheticOptional.textContent = '(Required)';
                syntheticOptional.className = 'text-danger';
                realRequired.textContent = '(Optional)';
                realRequired.className = 'text-muted';
                realZone.style.opacity = '0.6';
                syntheticZone.style.opacity = '1';
                numRowsContainer.style.display = 'none';
            }
        }

        function showSection(section) {
            document.querySelectorAll('section').forEach(s => s.style.display = 'none');
            document.getElementById(section + '-section').style.display = 'block';
            
            if (section === 'blockchain') {
                loadBlockchainStats();
            }
        }

        function updateLabel(type) {
            const input = document.getElementById(type + 'File');
            const label = document.getElementById(type + 'FileLabel');
            if (input.files.length > 0) {
                label.textContent = '✓ ' + input.files[0].name;
                label.classList.add('text-success');
            }
        }
        
        let startTime = null;
        let stepTimes = {1: 2, 2: 5, 3: 8}; // Estimated seconds per step
        let currentStep = 0;
        let timerInterval = null;
        
        let currentMode = 'generate';
        let totalSteps = 3;
        
        function updateProgress(step, message, subStatus = '') {
            currentStep = step;
            if (step === 1) startTime = Date.now();
            
            const mode = document.querySelector('input[name="mode"]:checked')?.value || 'generate';
            currentMode = mode;
            totalSteps = mode === 'generate' ? 3 : 2;
            
            const totalEstimated = mode === 'generate' ? stepTimes[1] + stepTimes[2] + stepTimes[3] : stepTimes[1] + stepTimes[3];
            const completedTime = Object.keys(stepTimes)
                .filter(s => parseInt(s) < step)
                .reduce((sum, s) => sum + stepTimes[s], 0);
            const remainingTime = Math.max(0, totalEstimated - completedTime);
            
            // Dynamic steps based on mode
            let steps;
            if (mode === 'generate') {
                steps = [
                    {num: 1, label: 'Upload & Parse Real Data', key: 1},
                    {num: 2, label: 'Generate Synthetic Data', key: 2},
                    {num: 3, label: 'Run Verification & Compliance Check', key: 3}
                ];
            } else if (mode === 'upload') {
                steps = [
                    {num: 1, label: 'Upload & Parse Both Datasets', key: 1},
                    {num: 2, label: 'Run Verification & Compliance Check', key: 3}
                ];
            } else { // synthetic_only
                steps = [
                    {num: 1, label: 'Upload & Parse Synthetic Data', key: 1},
                    {num: 2, label: 'Run Quality Analysis', key: 3}
                ];
            }
            
            const stepHtml = steps.map((s, idx) => {
                const isActive = step === s.key;
                const isDone = step > s.key;
                const isPending = step < s.key;
                return `
                    <div class="d-flex align-items-center mb-2 ${isDone ? 'text-success' : (isActive ? 'text-primary' : 'text-muted')}">
                        <i class="bi ${isDone ? 'bi-check-circle-fill' : (isActive ? 'bi-arrow-right-circle-fill text-primary' : 'bi-circle')} me-2"></i>
                        <span ${isActive ? 'class="fw-bold"' : ''}>${s.num}. ${s.label}</span>
                        ${isActive ? '<span class="ms-auto badge bg-primary">In Progress</span>' : (isDone ? '<span class="ms-auto badge bg-success">Done</span>' : '')}
                    </div>
                `;
            }).join('');
            
            const progressPercent = mode === 'upload' ? 
                (step === 1 ? 33 : (step >= 3 ? 100 : 66)) :
                (step / 3) * 100;
            
            const progressHtml = `
                <div class="card shadow-lg" style="max-width: 550px; margin: 0 auto;">
                    <div class="card-body p-4">
                        <div class="text-center mb-4">
                            <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
                            <h4 class="mb-1">Processing ${mode === 'generate' ? 'Generation & Verification' : (mode === 'upload' ? 'Uploaded Data' : 'Synthetic Data Analysis')}</h4>
                            <p class="text-muted mb-0">Step ${steps.findIndex(s => s.key === step) + 1} of ${steps.length}</p>
                        </div>
                        
                        <div class="progress mb-4" style="height: 12px; border-radius: 6px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                 style="width: ${progressPercent}%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"></div>
                        </div>
                        
                        <!-- Step Status -->
                        <div class="mb-4">
                            ${stepHtml}
                        </div>
                        
                        <!-- Current Action -->
                        <div class="alert alert-light border mb-3">
                            <div class="d-flex align-items-center">
                                <div class="spinner-grow spinner-grow-sm text-primary me-2" role="status"></div>
                                <div>
                                    <strong>${message}</strong>
                                    ${subStatus ? '<br><small class="text-muted">' + subStatus + '</small>' : ''}
                                </div>
                            </div>
                        </div>
                        
                        <!-- Timer -->
                        <div class="text-center">
                            <div class="d-flex justify-content-between text-muted small">
                                <span><i class="bi bi-clock me-1"></i>Elapsed: <span id="elapsedTime">0s</span></span>
                                <span>Est. remaining: <span id="remainingTime">~${remainingTime}s</span></span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('loading').innerHTML = progressHtml;
            
            // Start timer
            if (timerInterval) clearInterval(timerInterval);
            timerInterval = setInterval(updateTimer, 1000);
        }
        
        function updateTimer() {
            if (!startTime) return;
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const elapsedEl = document.getElementById('elapsedTime');
            if (elapsedEl) elapsedEl.textContent = elapsed + 's';
            
            // Update remaining estimate
            const totalEstimated = stepTimes[1] + stepTimes[2] + stepTimes[3];
            const remaining = Math.max(0, totalEstimated - elapsed);
            const remainingEl = document.getElementById('remainingTime');
            if (remainingEl) remainingEl.textContent = remaining > 0 ? '~' + remaining + 's' : 'Almost done...';
        }
        
        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }

        async function uploadAndVerify() {
            const realFile = document.getElementById('realFile').files[0];
            const syntheticFile = document.getElementById('syntheticFile').files[0];
            const mode = document.querySelector('input[name="mode"]:checked').value;
            
            // Validation based on mode
            if (mode === 'generate') {
                if (!realFile) {
                    alert('Real dataset is required for Generate & Verify mode');
                    return;
                }
            } else if (mode === 'upload') {
                if (!realFile || !syntheticFile) {
                    alert('Both real and synthetic datasets are required for Upload Both mode');
                    return;
                }
            } else if (mode === 'synthetic_only') {
                if (!syntheticFile) {
                    alert('Synthetic dataset is required for Synthetic Only mode');
                    return;
                }
            }

            // Update step estimates based on mode
            const needsGeneration = mode === 'generate' && !syntheticFile;
            stepTimes = needsGeneration ? {1: 2, 2: 5, 3: 8} : {1: 2, 2: 0, 3: 8};

            document.getElementById('loading').style.display = 'block';
            document.getElementById('upload-section').style.display = 'none';
            startTime = Date.now();

            try {
                // Step 1: Upload data
                const uploadMessage = mode === 'synthetic_only' ? 
                    'Uploading synthetic data...' : 
                    (mode === 'upload' ? 'Uploading both datasets...' : 'Uploading real data...');
                updateProgress(1, uploadMessage, 'Parsing CSV files and validating columns');
                
                const formData = new FormData();
                formData.append('mode', mode);
                if (realFile) {
                    formData.append('real_file', realFile);
                }
                if (syntheticFile) {
                    formData.append('synthetic_file', syntheticFile);
                }
                formData.append('categorical_columns', document.getElementById('categoricalCols').value);
                formData.append('protected_attributes', document.getElementById('protectedAttrs').value);
                formData.append('target_column', document.getElementById('targetCol').value);
                
                // Add preprocessing option
                const preprocessEnabled = document.getElementById('enablePreprocessing').checked;
                formData.append('preprocess', preprocessEnabled ? 'true' : 'false');

                const uploadResponse = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                const uploadResult = await uploadResponse.json();
                
                if (uploadResult.error) {
                    throw new Error(uploadResult.error);
                }

                currentUploadId = uploadResult.upload_id;
                console.log('Upload result:', uploadResult);
                
                // Store preprocessing report if available
                currentPreprocessingReport = uploadResult.preprocessing || null;
                if (currentPreprocessingReport) {
                    console.log('Preprocessing applied:', currentPreprocessingReport);
                }
                
                // Step 2: Generate synthetic data if needed (only for generate mode)
                if (mode === 'generate' && (uploadResult.needs_generation || !syntheticFile)) {
                    updateProgress(2, 'Generating synthetic data...', 'Using statistical sampling to create privacy-preserving data');
                    
                    const numRows = document.getElementById('numRows').value;
                    const genResponse = await fetch('/api/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            upload_id: currentUploadId,
                            num_rows: numRows ? parseInt(numRows) : null,
                            use_cached: true
                        })
                    });
                    const genResult = await genResponse.json();
                    
                    if (genResult.error) {
                        throw new Error(genResult.error);
                    }
                    
                    console.log('Generation result:', genResult);
                } else {
                    console.log('Skipping generation - mode:', mode);
                }

                // Step 3: Run verification
                const verifyMessage = mode === 'synthetic_only' ? 
                    'Running quality analysis...' : 
                    'Running distributed verification...';
                const verifySubMessage = mode === 'synthetic_only' ?
                    'Analyzing synthetic data quality metrics' :
                    'Checking privacy, utility, and fairness metrics with multiple verifiers';
                updateProgress(3, verifyMessage, verifySubMessage);
                
                const verifyResponse = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        upload_id: currentUploadId,
                        num_verifiers: parseInt(document.getElementById('numVerifiers').value)
                    })
                });
                const verifyResult = await verifyResponse.json();
                
                if (verifyResult.error) {
                    throw new Error(verifyResult.error);
                }

                console.log('Verification result:', verifyResult);
                currentRequestId = verifyResult.request_id;
                
                // Show download synthetic data button if data was generated
                if (needsGeneration) {
                    generatedDataAvailable = true;
                    document.getElementById('downloadSyntheticDiv').style.display = 'block';
                } else {
                    document.getElementById('downloadSyntheticDiv').style.display = 'none';
                }
                
                stopTimer();
                displayResults(verifyResult.verification_result);
                
            } catch (error) {
                console.error('Error:', error);
                stopTimer();
                alert('Error: ' + error.message);
                document.getElementById('loading').style.display = 'none';
                showSection('upload');
            } finally {
                document.getElementById('loading').style.display = 'none';
                stopTimer();
            }
        }

        function displayResults(result) {
            showSection('results');
            
            console.log('Display results:', result);
            
            const consensus = result.consensus || {};
            const scores = consensus.final_scores || {};
            
            // Extract scores - handle both naming conventions
            const privacyScore = scores.privacy_score ?? scores.privacy ?? 0;
            const utilityScore = scores.utility_score ?? scores.utility ?? 0;
            const biasScore = scores.bias_score ?? scores.bias ?? 0;
            const overallScore = scores.overall_score ?? scores.overall ?? 0;
            
            // Update scores with animation
            animateScore('privacy', privacyScore);
            animateScore('utility', utilityScore);
            animateScore('bias', biasScore);
            animateScore('overall', overallScore);
            
            // Update status - check both 'approved' boolean and 'status' string
            const approved = consensus.approved === true || consensus.status === 'approved';
            const statusBadge = document.getElementById('statusBadge');
            statusBadge.textContent = approved ? 'APPROVED' : 'REJECTED';
            statusBadge.className = 'status-badge ' + (approved ? 'status-approved' : 'status-rejected');
            
            // Update consensus details
            document.getElementById('requestId').textContent = currentRequestId || '--';
            document.getElementById('verifierCount').textContent = consensus.num_verifiers || '--';
            document.getElementById('consensusScore').textContent = 
                overallScore ? overallScore.toFixed(2) + '%' : '--';
            document.getElementById('dataHash').textContent = result.data_hash ? result.data_hash.substring(0, 16) + '...' : '--';
            
            // Update compliance with the extracted scores
            updateComplianceStatus({
                privacy_score: privacyScore,
                utility_score: utilityScore,
                bias_score: biasScore,
                overall_score: overallScore
            });
            
            // Display preprocessing report if available
            displayPreprocessingReport();
            
            // Load audit trail
            loadAuditTrail();
            
            // Load blockchain stats
            loadBlockchainStats();
        }
        
        function displayPreprocessingReport() {
            const reportRow = document.getElementById('preprocessingReportRow');
            
            if (!currentPreprocessingReport || !currentPreprocessingReport.preprocessing_complete) {
                reportRow.style.display = 'none';
                return;
            }
            
            reportRow.style.display = 'block';
            const report = currentPreprocessingReport;
            
            // Update shape info
            document.getElementById('prepOriginalShape').textContent = 
                report.original_shape ? `${report.original_shape[0]} rows × ${report.original_shape[1]} cols` : '--';
            document.getElementById('prepFinalShape').textContent = 
                report.final_shape ? `${report.final_shape[0]} rows × ${report.final_shape[1]} cols` : '--';
            
            // Update steps applied
            const stepsContainer = document.getElementById('prepStepsApplied');
            if (report.steps_applied && report.steps_applied.length > 0) {
                const stepLabels = {
                    'normalized_column_names': '<span class="badge bg-info me-1">Column Names Normalized</span>',
                    'date_columns_processed': '<span class="badge bg-primary me-1">Date Columns Processed</span>',
                    'duplicates_removed': '<span class="badge bg-warning me-1">Duplicates Removed</span>',
                    'missing_values_handled': '<span class="badge bg-success me-1">Missing Values Handled</span>',
                    'outliers_clipped': '<span class="badge bg-secondary me-1">Outliers Clipped</span>'
                };
                stepsContainer.innerHTML = report.steps_applied.map(step => 
                    stepLabels[step] || `<span class="badge bg-light text-dark me-1">${step}</span>`
                ).join('');
            } else {
                stepsContainer.innerHTML = '<span class="text-muted">No preprocessing steps needed</span>';
            }
            
            // Update details
            const detailsContainer = document.getElementById('prepDetails');
            let detailsHtml = '<div class="row">';
            
            // Duplicates removed
            if (report.duplicates_removed) {
                detailsHtml += `
                    <div class="col-md-4 mb-2">
                        <div class="alert alert-warning py-2 mb-0">
                            <small><strong><i class="bi bi-dash-circle me-1"></i>Duplicates:</strong> ${report.duplicates_removed} rows removed</small>
                        </div>
                    </div>`;
            }
            
            // Missing values imputed
            if (report.missing_values_imputed) {
                detailsHtml += `
                    <div class="col-md-4 mb-2">
                        <div class="alert alert-success py-2 mb-0">
                            <small><strong><i class="bi bi-check-circle me-1"></i>Missing Values:</strong> ${report.missing_values_imputed} values imputed</small>
                        </div>
                    </div>`;
            }
            
            // Outliers handled
            if (report.outliers_handled && report.outliers_handled.length > 0) {
                const totalOutliers = report.outliers_handled.reduce((sum, o) => sum + o.outliers_clipped, 0);
                detailsHtml += `
                    <div class="col-md-4 mb-2">
                        <div class="alert alert-secondary py-2 mb-0">
                            <small><strong><i class="bi bi-sliders me-1"></i>Outliers:</strong> ${totalOutliers} values clipped in ${report.outliers_handled.length} columns</small>
                        </div>
                    </div>`;
            }
            
            detailsHtml += '</div>';
            
            // Columns modified details
            if (report.columns_modified && report.columns_modified.length > 0) {
                detailsHtml += '<h6 class="mt-3 mb-2 text-muted"><i class="bi bi-columns me-1"></i>Column Modifications</h6>';
                detailsHtml += '<div class="table-responsive"><table class="table table-sm table-striped mb-0"><thead><tr><th>Column</th><th>Action</th><th>Details</th></tr></thead><tbody>';
                
                report.columns_modified.slice(0, 10).forEach(mod => {
                    let details = '';
                    if (mod.fill_value !== undefined) details = `Value: ${mod.fill_value}`;
                    if (mod.reason) details = mod.reason;
                    if (mod.new_columns) details = `New: ${mod.new_columns.join(', ')}`;
                    
                    const actionLabels = {
                        'imputed_median': 'Filled with median',
                        'imputed_mode': 'Filled with mode',
                        'imputed_unknown': 'Filled with "Unknown"',
                        'dropped': 'Dropped (too many nulls)',
                        'date_expanded': 'Expanded to date parts',
                        'converted_to_category': 'Converted to category',
                        'converted_float_to_int': 'Converted to integer'
                    };
                    
                    detailsHtml += `<tr><td><code>${mod.column}</code></td><td>${actionLabels[mod.action] || mod.action}</td><td><small class="text-muted">${details}</small></td></tr>`;
                });
                
                if (report.columns_modified.length > 10) {
                    detailsHtml += `<tr><td colspan="3" class="text-muted">... and ${report.columns_modified.length - 10} more modifications</td></tr>`;
                }
                
                detailsHtml += '</tbody></table></div>';
            }
            
            detailsContainer.innerHTML = detailsHtml;
        }
        
        function animateScore(type, targetScore) {
            const scoreEl = document.getElementById(type + 'Score');
            const barEl = document.getElementById(type + 'Bar');
            
            if (targetScore === undefined || targetScore === null) {
                scoreEl.textContent = '--';
                return;
            }
            
            // Define thresholds for each type
            const thresholds = {
                'privacy': 70,
                'utility': 70,
                'bias': 80,
                'overall': 70
            };
            
            const threshold = thresholds[type] || 70;
            const passes = targetScore >= threshold;
            
            // Update bar color based on pass/fail
            barEl.className = 'progress-bar ' + (passes ? 'bg-success' : 'bg-danger');
            
            let currentScore = 0;
            const duration = 1000;
            const steps = 30;
            const increment = targetScore / steps;
            const stepDuration = duration / steps;
            
            const animate = () => {
                currentScore += increment;
                if (currentScore >= targetScore) {
                    currentScore = targetScore;
                    scoreEl.textContent = targetScore.toFixed(1);
                    barEl.style.width = targetScore + '%';
                    // Add pass/fail indicator
                    scoreEl.className = 'metric-value ' + (passes ? 'text-success' : 'text-danger');
                } else {
                    scoreEl.textContent = currentScore.toFixed(1);
                    barEl.style.width = currentScore + '%';
                    setTimeout(animate, stepDuration);
                }
            };
            animate();
        }

        function updateScore(type, score) {
            const scoreEl = document.getElementById(type + 'Score');
            const barEl = document.getElementById(type + 'Bar');
            
            if (score !== undefined && score !== null) {
                scoreEl.textContent = score.toFixed(1);
                barEl.style.width = score + '%';
            }
        }

        function updateComplianceStatus(scores) {
            // Handle both naming conventions
            const privacyScore = scores.privacy_score ?? scores.privacy ?? 0;
            const utilityScore = scores.utility_score ?? scores.utility ?? 0;
            const biasScore = scores.bias_score ?? scores.bias ?? 0;
            const overallScore = scores.overall_score ?? scores.overall ?? 0;
            
            // Updated thresholds based on actual system requirements
            const privacyPass = privacyScore >= 70;  // Target: 70%
            const utilityPass = utilityScore >= 70;  // Target: 70%
            const biasPass = biasScore >= 80;        // Target: 80% (stricter for fairness)
            
            // GDPR: Requires privacy (>=70) and fairness (>=70)
            const gdprPass = privacyScore >= 70 && biasScore >= 70;
            // HIPAA: Requires strong privacy (>=70) for de-identification
            const hipaaPass = privacyScore >= 70;
            // EU AI Act: Requires fairness/bias (>=80) and overall quality (>=70)
            const euAiActPass = biasScore >= 80 && overallScore >= 70;
            
            document.getElementById('privacyStatus').textContent = privacyPass ? 'PASS' : 'FAIL';
            document.getElementById('privacyStatus').className = 'badge ' + (privacyPass ? 'bg-success' : 'bg-danger');
            
            document.getElementById('utilityStatus').textContent = utilityPass ? 'PASS' : 'FAIL';
            document.getElementById('utilityStatus').className = 'badge ' + (utilityPass ? 'bg-success' : 'bg-danger');
            
            document.getElementById('fairnessStatus').textContent = biasPass ? 'PASS' : 'FAIL';
            document.getElementById('fairnessStatus').className = 'badge ' + (biasPass ? 'bg-success' : 'bg-danger');
            
            document.getElementById('gdprStatus').textContent = gdprPass ? 'COMPLIANT' : 'NON-COMPLIANT';
            document.getElementById('gdprStatus').className = 'badge ' + (gdprPass ? 'bg-success' : 'bg-danger');
            
            document.getElementById('hipaaStatus').textContent = hipaaPass ? 'COMPLIANT' : 'NON-COMPLIANT';
            document.getElementById('hipaaStatus').className = 'badge ' + (hipaaPass ? 'bg-success' : 'bg-danger');
            
            document.getElementById('euAiActStatus').textContent = euAiActPass ? 'COMPLIANT' : 'NON-COMPLIANT';
            document.getElementById('euAiActStatus').className = 'badge ' + (euAiActPass ? 'bg-success' : 'bg-danger');

            const explainEl = document.getElementById('complianceExplain');
            const detailCard = (title, pass, reason) => `
                <div class="compliance-detail ${pass ? 'pass' : 'fail'}">
                    <div class="compliance-title">${title}: ${pass ? 'PASS' : 'FAIL'}</div>
                    <p class="compliance-reason">${reason}</p>
                </div>
            `;

            const privacyReason = privacyPass
                ? `Privacy score is ${privacyScore.toFixed(1)}%, meeting the ≥70% threshold.`
                : `Privacy score is ${privacyScore.toFixed(1)}%, below the required ≥70%. Improve de-identification or reduce memorization.`;

            const utilityReason = utilityPass
                ? `Utility score is ${utilityScore.toFixed(1)}%, meeting the ≥70% threshold.`
                : `Utility score is ${utilityScore.toFixed(1)}%, below the required ≥70%. Improve statistical similarity and ML efficacy.`;

            const fairnessReason = biasPass
                ? `Fairness score is ${biasScore.toFixed(1)}%, meeting the stricter ≥80% threshold.`
                : `Fairness score is ${biasScore.toFixed(1)}%, below ≥80%. Bias mitigation is needed for protected groups.`;

            const gdprReason = gdprPass
                ? `GDPR rule passed because Privacy (${privacyScore.toFixed(1)}%) and Fairness (${biasScore.toFixed(1)}%) are both ≥70%.`
                : `GDPR rule failed: requires Privacy ≥70% and Fairness ≥70%, but got Privacy ${privacyScore.toFixed(1)}%, Fairness ${biasScore.toFixed(1)}%.`;

            const hipaaReason = hipaaPass
                ? `HIPAA rule passed because Privacy is ${privacyScore.toFixed(1)}% (≥70%).`
                : `HIPAA rule failed because Privacy is ${privacyScore.toFixed(1)}%, below ≥70%.`;

            const euAiActReason = euAiActPass
                ? `EU AI Act rule passed because Fairness (${biasScore.toFixed(1)}%) is ≥80% and Overall (${overallScore.toFixed(1)}%) is ≥70%.`
                : `EU AI Act rule failed: requires Fairness ≥80% and Overall ≥70%, but got Fairness ${biasScore.toFixed(1)}%, Overall ${overallScore.toFixed(1)}%.`;

            explainEl.innerHTML = [
                detailCard('Privacy Quality Check', privacyPass, privacyReason),
                detailCard('Utility Quality Check', utilityPass, utilityReason),
                detailCard('Fairness Quality Check', biasPass, fairnessReason),
                detailCard('GDPR Compliance', gdprPass, gdprReason),
                detailCard('HIPAA Compliance', hipaaPass, hipaaReason),
                detailCard('EU AI Act Compliance', euAiActPass, euAiActReason)
            ].join('');
        }

        async function loadAuditTrail() {
            if (!currentRequestId) return;
            
            try {
                const response = await fetch('/api/audit/' + currentRequestId);
                const result = await response.json();
                
                const timeline = document.getElementById('auditTimeline');
                let entries = result.audit_trail || [];
                
                // Handle both array and object structures
                if (!Array.isArray(entries)) {
                    entries = entries.entries || [];
                }
                
                if (entries.length === 0) {
                    timeline.innerHTML = '<p class="text-muted">No audit entries found.</p>';
                    return;
                }

                const escapeHtml = (value) => String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;');

                const scorePill = (label, value, threshold = 70) => {
                    if (value === undefined || value === null) return '';
                    const num = Number(value);
                    const css = num >= threshold ? 'pill-success' : 'pill-danger';
                    return `<span class="audit-pill ${css}">${label}: ${num.toFixed(1)}%</span>`;
                };

                const renderAuditDetails = (entry) => {
                    const payload = entry.payload || entry.details || entry.data || {};
                    if (!payload || Object.keys(payload).length === 0) {
                        return '<div class="audit-kv">No payload details</div>';
                    }

                    if (payload.event === 'data_generation') {
                        return `
                            <div class="audit-kv"><strong>Generator:</strong> ${escapeHtml(payload.generator_type || 'unknown')}</div>
                            <div class="audit-kv"><strong>Rows:</strong> ${escapeHtml(payload.parameters?.num_rows || 'same as real')}</div>
                            <div class="audit-kv"><strong>Upload ID:</strong> ${escapeHtml(payload.parameters?.upload_id || 'n/a')}</div>
                        `;
                    }

                    if (payload.event === 'verification_submission' && payload.results) {
                        const r = payload.results;
                        return `
                            <div class="audit-kv"><strong>Verifier:</strong> ${escapeHtml(payload.verifier_id || 'unknown')}</div>
                            <div>${scorePill('Privacy', r.privacy_score)}${scorePill('Utility', r.utility_score)}${scorePill('Bias', r.bias_score, 80)}</div>
                        `;
                    }

                    if (payload.event === 'consensus_reached' && payload.consensus_result) {
                        const c = payload.consensus_result;
                        const fs = c.final_scores || {};
                        const statusClass = (c.status || '').toLowerCase() === 'approved' ? 'pill-success' : 'pill-danger';
                        return `
                            <div><span class="audit-pill ${statusClass}">Status: ${escapeHtml((c.status || 'unknown').toUpperCase())}</span><span class="audit-pill pill-info">Verifiers: ${escapeHtml(c.num_verifiers || 0)}</span></div>
                            <div>${scorePill('Privacy', fs.privacy)}${scorePill('Utility', fs.utility)}${scorePill('Bias', fs.bias, 80)}${scorePill('Overall', fs.overall)}</div>
                        `;
                    }

                    return `<pre class="mb-0"><small>${escapeHtml(JSON.stringify(payload, null, 2))}</small></pre>`;
                };
                
                timeline.innerHTML = entries.map(entry => `
                    <div class="timeline-item">
                        <strong>${entry.event_type || entry.entry_type || 'Event'}</strong>
                        <p class="text-muted mb-1">${entry.timestamp || '--'}</p>
                        <div class="audit-card">
                            ${renderAuditDetails(entry)}
                        </div>
                    </div>
                `).join('');
                
            } catch (error) {
                console.error('Error loading audit trail:', error);
            }
        }

        async function loadBlockchainStats() {
            try {
                const response = await fetch('/api/blockchain/stats');
                const result = await response.json();
                
                const blockchain = result.blockchain || {};
                document.getElementById('blockCount').textContent = blockchain.total_blocks || 0;
                document.getElementById('entryCount').textContent = blockchain.total_entries || 0;
                document.getElementById('chainValid').textContent = blockchain.is_valid ? 'Valid ✓' : 'Invalid ✗';
                document.getElementById('chainValid').className = 'metric-value ' + (blockchain.is_valid ? 'text-success' : 'text-danger');
                
                // Update blockchain explorer
                updateBlockchainExplorer(blockchain);
                
            } catch (error) {
                console.error('Error loading blockchain stats:', error);
            }
        }
        
        function updateBlockchainExplorer(blockchain) {
            const blocksContainer = document.getElementById('blockchainBlocks');
            const blocks = blockchain.recent_blocks || [];
            
            if (blocks.length === 0) {
                blocksContainer.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-link-45deg fs-1 text-muted"></i>
                        <p class="text-muted mt-2">Blockchain initialized. ${blockchain.total_blocks || 0} block(s) recorded.</p>
                    </div>
                `;
                return;
            }
            
            blocksContainer.innerHTML = blocks.map((block, i) => `
                <div class="audit-entry">
                    <div class="d-flex justify-content-between">
                        <strong>Block #${block.index || i}</strong>
                        <small class="text-muted">${block.timestamp || '--'}</small>
                    </div>
                    <p class="mb-1 small">Entries: ${block.entries?.length || 0}</p>
                    <div class="mini-hash mb-2">Hash: ${(block.hash || '').substring(0, 48)}...</div>
                    <div>
                        ${(block.entries || []).slice(0, 3).map(e => `<span class="audit-pill pill-info">${e.entry_type || 'event'}</span>`).join('')}
                        ${(block.entries || []).length > 3 ? `<span class="audit-pill pill-warning">+${(block.entries || []).length - 3} more</span>` : ''}
                    </div>
                </div>
            `).join('');
        }

        async function downloadReport(format = 'json') {
            if (!currentRequestId) {
                alert('No verification to download');
                return;
            }
            window.location.href = '/api/compliance/' + currentRequestId + '/download?format=' + format;
        }
        
        async function downloadGeneratedData() {
            if (!currentUploadId) {
                alert('No generated data available');
                return;
            }
            window.location.href = '/api/download/synthetic/' + currentUploadId;
        }

        // Initial load
        loadBlockchainStats();
        updateModeUI();
    