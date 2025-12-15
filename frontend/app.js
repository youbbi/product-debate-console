// WebSocket connection
let ws = null;
let debateInProgress = false;
let executiveData = {};  // Store parsed data for comparison view
let executivePhases = {};  // Track phase state per exec: { cfo: { phase, timeline: [], inputSummary } }
let isComparisonView = false;
let selectedMethod = 'consensus';  // 'consensus', 'council', or 'both'
let councilData = {};  // Store council LLM responses for visualization
let councilStage = null;  // Current stage: 'divergence', 'convergence', 'synthesis'

// Default question from Debate questions.txt
const DEFAULT_QUESTION = `Should I pursue building my own application, which is a meal planning it's aimed for B2C. I think the unique advantage is how it's personalising the meal suggestions based on your preferences. It's smart, it always kind of anticipates your needs, it can parse any type of recipes and generates automatically your weekly meal plan based on all your most preferred recipes.
So my question to this group is: We're a small start-up and it's a very crowded market, so is there any way we can make money out of this application?`;

// DOM Elements
const startButton = document.getElementById('startButton');
const questionInput = document.getElementById('question');
const statusMessage = document.getElementById('status');
const executivesGrid = document.getElementById('executivesGrid');
const decisionPanel = document.getElementById('decisionPanel');
const consensusBar = document.getElementById('consensusBar');
const consensusText = document.getElementById('consensusText');
const recommendationBadge = document.getElementById('recommendationBadge');
const decisionOutput = document.getElementById('decisionOutput');

const EXECUTIVES = [
    { role: 'cpo', name: 'Jamie Rodriguez', title: 'Chief Product Officer', emoji: '🎯' },
    { role: 'cfo', name: 'Alex Chen', title: 'Chief Financial Officer', emoji: '💰' },
    { role: 'cto', name: 'Sam Park', title: 'Chief Technology Officer', emoji: '⚙️' },
    { role: 'cro', name: 'Taylor Morgan', title: 'Chief Revenue Officer', emoji: '📈' }
];

// ============================================================================
// WebSocket Setup
// ============================================================================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('✓ Connected to debate console');
        showStatus('Connected and ready', 'success');
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showStatus('Connection error', 'error');
    };

    ws.onclose = () => {
        console.log('Disconnected from debate console');
        showStatus('Disconnected. Reconnecting...', 'error');
        setTimeout(connectWebSocket, 3000);
    };
}

// ============================================================================
// Message Handler
// ============================================================================

function handleMessage(message) {
    switch (message.type) {
        case 'debate_started':
            initializeDebateUI(message.method || selectedMethod);
            const methodLabel = message.method === 'council' ? 'LLM Council' :
                               message.method === 'both' ? 'Both methods' : 'Executive Consensus';
            showStatus(`${methodLabel} starting...`, 'loading');
            break;

        case 'exec_started':
            initExecutivePhase(message.role, message.input_summary, message.timestamp);
            showStatus(`${message.name} starting analysis...`, 'loading');
            break;

        case 'exec_streaming':
            // Transition to analyzing on first token
            if (executivePhases[message.role]?.phase === 'starting') {
                updatePhase(message.role, 'analyzing', message.timestamp);
            }
            updateExecutiveOutput(message.role, message.name, message.emoji, message.title, message.token, true);
            break;

        case 'exec_complete':
            updatePhase(message.role, 'complete', message.timestamp);
            completeExecutiveOutput(message.role, message.name, message.emoji, message.title, message.output);
            showStatus(`${message.name} analysis complete`, 'success');
            break;

        case 'consensus_update':
            updateConsensus(message.consensus);
            break;

        case 'final_decision':
            showFinalDecision(message.decision);
            break;

        case 'context_established':
            console.log('Evaluation lenses:', message.lenses);
            break;

        case 'error':
            showStatus(`Error: ${message.message}`, 'error');
            debateInProgress = false;
            startButton.disabled = false;
            break;

        // ============================================================================
        // Council Events
        // ============================================================================

        case 'council_divergence_start':
            initializeCouncilUI(message.providers);
            updateCouncilStage('divergence');
            showStatus('Council divergence: LLMs analyzing...', 'loading');
            break;

        case 'council_response_streaming':
            updateCouncilResponse(message.provider_id, message.token, true);
            break;

        case 'council_response_complete':
            completeCouncilResponse(message.provider_id, message.response, message.parsed_data);
            break;

        case 'council_peer_review_start':
            updateCouncilStage('convergence');
            showStatus('Peer review: LLMs evaluating each other...', 'loading');
            break;

        case 'council_peer_review':
            updatePeerReview(message.reviewer_id, message.target_id, message.score);
            break;

        case 'council_rating_matrix':
            renderRatingMatrix(message.matrix);
            break;

        case 'council_synthesis_start':
            updateCouncilStage('synthesis');
            showStatus('Chairman synthesizing final decision...', 'loading');
            break;

        case 'council_synthesis_streaming':
            // Could stream chairman's synthesis if needed
            break;

        case 'council_final_decision':
            showCouncilDecision(message.decision, message.chairman_provider);
            break;

        // ============================================================================
        // Comparison Events (Both method)
        // ============================================================================

        case 'comparison_started':
            showStatus('Running both methods in parallel...', 'loading');
            break;

        case 'comparison_complete':
            showComparisonResults(message.consensus, message.council, message.comparison);
            break;
    }
}

// ============================================================================
// UI Updates
// ============================================================================

function initializeDebateUI(method = 'consensus') {
    debateInProgress = true;
    startButton.disabled = true;
    decisionPanel.style.display = 'none';
    executiveData = {};  // Reset stored data
    executivePhases = {};  // Reset phase tracking
    councilData = {};  // Reset council data
    councilStage = null;

    // Show appropriate view based on method
    const singleView = document.getElementById('singleView');
    const sideBySideView = document.getElementById('sideBySideView');
    const consensusView = document.getElementById('consensusView');
    const councilView = document.getElementById('councilView');

    if (method === 'both') {
        singleView.style.display = 'none';
        sideBySideView.style.display = 'block';
        // Initialize both sides
        initializeConsensusSide();
        initializeCouncilSide();
    } else {
        singleView.style.display = 'block';
        sideBySideView.style.display = 'none';

        if (method === 'council') {
            consensusView.style.display = 'none';
            councilView.style.display = 'block';
        } else {
            consensusView.style.display = 'block';
            councilView.style.display = 'none';
            // Initialize consensus view
            executivesGrid.innerHTML = '';
            EXECUTIVES.forEach(exec => {
                const card = createExecutiveCard(exec);
                executivesGrid.appendChild(card);
            });
        }
    }

    // Reset comparison view
    const comparisonBody = document.getElementById('comparisonBody');
    if (comparisonBody) {
        comparisonBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;">Waiting for executive analysis...</td></tr>';
    }
}

function initializeConsensusSide() {
    const grid = document.getElementById('executivesGridLeft');
    if (!grid) return;
    grid.innerHTML = '';
    EXECUTIVES.forEach(exec => {
        const card = createExecutiveCard(exec, true);  // true = mini version
        grid.appendChild(card);
    });
}

function initializeCouncilSide() {
    const grid = document.getElementById('councilResponsesRight');
    if (!grid) return;
    grid.innerHTML = '<div class="waiting-message">Waiting for council to start...</div>';
}

function createExecutiveCard(exec, mini = false) {
    const card = document.createElement('div');
    card.className = `executive-card${mini ? ' mini' : ''}`;
    card.id = `exec-${exec.role}${mini ? '-mini' : ''}`;

    if (mini) {
        card.innerHTML = `
            <div class="executive-header">
                <div class="executive-emoji">${exec.emoji}</div>
                <div class="executive-info">
                    <h4>${exec.name}</h4>
                </div>
                <div class="phase-indicator">Waiting...</div>
            </div>
            <div class="executive-output" id="output-${exec.role}-mini">
                <span style="color: #64748b; font-style: italic;">Waiting...</span>
            </div>
        `;
    } else {
        card.innerHTML = `
            <div class="executive-header">
                <div class="executive-emoji">${exec.emoji}</div>
                <div class="executive-info">
                    <h4>${exec.name}</h4>
                    <p>${exec.title}</p>
                </div>
                <div class="phase-indicator">Waiting...</div>
            </div>
            <div class="input-summary"></div>
            <div class="exec-timeline"></div>
            <div class="executive-output" id="output-${exec.role}">
                <span style="color: #64748b; font-style: italic;">Waiting for analysis...</span>
            </div>
        `;
    }
    return card;
}

function updateExecutiveOutput(role, name, emoji, title, token, streaming) {
    const outputElement = document.getElementById(`output-${role}`);
    const card = document.getElementById(`exec-${role}`);

    if (!outputElement) return;

    // Clear "Waiting..." on first token
    if (outputElement.textContent.includes('Waiting for analysis...')) {
        outputElement.innerHTML = '';
    }

    // Append token
    outputElement.textContent += token;
    outputElement.parentElement.scrollTop = outputElement.parentElement.scrollHeight;

    // Update card status
    if (card) {
        card.classList.add('loading');
    }
}

// ============================================================================
// Phase Tracking & Timeline
// ============================================================================

function initExecutivePhase(role, inputSummary, timestamp) {
    executivePhases[role] = {
        phase: null,
        timeline: [],
        inputSummary: inputSummary
    };
    updatePhase(role, 'starting', timestamp);
    renderInputSummary(role, inputSummary);
}

function updatePhase(role, phase, timestamp) {
    if (!executivePhases[role]) {
        executivePhases[role] = { phase: null, timeline: [], inputSummary: null };
    }

    executivePhases[role].phase = phase;
    executivePhases[role].timeline.push({ phase, timestamp });

    renderPhaseIndicator(role, phase);
    renderTimeline(role);
}

function renderInputSummary(role, inputSummary) {
    const card = document.getElementById(`exec-${role}`);
    if (!card || !inputSummary) return;

    const summaryEl = card.querySelector('.input-summary');
    if (!summaryEl) return;

    const contextKeys = inputSummary.context_keys || [];
    const contextDisplay = contextKeys.length > 0
        ? `<div class="summary-context">Context: ${contextKeys.join(', ')}</div>`
        : '';

    summaryEl.innerHTML = `
        <div class="summary-label">Analyzing:</div>
        <div class="summary-query">"${inputSummary.query_preview || ''}"</div>
        ${contextDisplay}
        <div class="summary-focus">Focus: ${inputSummary.primary_concern || ''}</div>
    `;
}

function renderPhaseIndicator(role, phase) {
    const card = document.getElementById(`exec-${role}`);
    if (!card) return;

    // Update card class for styling
    card.classList.remove('phase-starting', 'phase-analyzing', 'phase-complete', 'loading');
    card.classList.add(`phase-${phase}`);
    if (phase === 'analyzing') {
        card.classList.add('loading');
    }

    // Update phase indicator in header
    const indicator = card.querySelector('.phase-indicator');
    if (!indicator) return;

    const phaseLabels = {
        starting: 'Starting...',
        analyzing: 'Analyzing...',
        complete: 'Complete'
    };

    indicator.className = `phase-indicator phase-${phase}`;
    indicator.textContent = phaseLabels[phase] || phase;
}

function renderTimeline(role) {
    const card = document.getElementById(`exec-${role}`);
    if (!card) return;

    const phases = executivePhases[role];
    if (!phases || phases.timeline.length === 0) return;

    const timelineEl = card.querySelector('.exec-timeline');
    if (!timelineEl) return;

    const timeline = phases.timeline;
    const allPhases = ['starting', 'analyzing', 'complete'];

    let html = '<div class="timeline-steps">';

    allPhases.forEach((phaseName, i) => {
        const entry = timeline.find(t => t.phase === phaseName);
        const isReached = !!entry;
        const isActive = phaseName === phases.phase;
        const isComplete = timeline.findIndex(t => t.phase === phaseName) < timeline.length - 1 ||
                          (phaseName === 'complete' && isReached);

        // Calculate duration to next phase
        let duration = '';
        if (entry && i < allPhases.length - 1) {
            const nextPhase = allPhases[i + 1];
            const nextEntry = timeline.find(t => t.phase === nextPhase);
            if (nextEntry) {
                const start = new Date(entry.timestamp);
                const end = new Date(nextEntry.timestamp);
                const diffMs = end - start;
                duration = formatDuration(diffMs);
            }
        }

        html += `
            <div class="timeline-step ${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''} ${isReached ? 'reached' : ''}">
                <div class="step-dot"></div>
                <div class="step-label">${capitalize(phaseName)}</div>
                ${entry ? `<div class="step-time">${formatTime(entry.timestamp)}</div>` : '<div class="step-time">--:--</div>'}
                ${duration ? `<div class="step-duration">${duration}</div>` : ''}
            </div>
        `;

        // Add connector line between steps
        if (i < allPhases.length - 1) {
            const nextReached = timeline.some(t => t.phase === allPhases[i + 1]);
            html += `<div class="timeline-connector ${nextReached ? 'complete' : ''}"></div>`;
        }
    });

    html += '</div>';
    timelineEl.innerHTML = html;
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

function formatDuration(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function completeExecutiveOutput(role, name, emoji, title, fullOutput) {
    const card = document.getElementById(`exec-${role}`);
    const outputElement = document.getElementById(`output-${role}`);

    if (card) {
        card.classList.remove('loading');
    }

    if (outputElement) {
        // Try to parse and format JSON output
        let displayContent;
        try {
            const parsed = JSON.parse(fullOutput);
            executiveData[role] = parsed;  // Store for comparison view
            displayContent = formatExecutiveAnalysis(parsed, role);

            // Update comparison view if visible
            if (isComparisonView) {
                renderComparisonTable();
            }
        } catch {
            // If not valid JSON, try to extract useful info and format nicely
            displayContent = formatMalformedOutput(fullOutput, role);
        }

        outputElement.innerHTML = displayContent;
        outputElement.parentElement.scrollTop = 0;
    }
}

function formatMalformedOutput(output, role) {
    // Try to extract key information from malformed JSON
    let html = '<div class="exec-analysis fallback-analysis">';

    // Extract recommendation patterns
    const recPatterns = {
        cfo: /financial_recommendation["\s:]+["']?(\w+)/i,
        cpo: /product_recommendation["\s:]+["']?(\w+)/i,
        cto: /technology_recommendation["\s:]+["']?(\w+)/i,
        cro: /revenue_recommendation["\s:]+["']?(\w+)/i
    };

    const recMatch = output.match(recPatterns[role] || /recommendation["\s:]+["']?(\w+)/i);
    if (recMatch) {
        html += `<div class="recommendation-row">
            <span class="rec-badge ${getRecClass(recMatch[1])}">${recMatch[1].toUpperCase()}</span>
        </div>`;
    }

    // Extract confidence level
    const confidenceMatch = output.match(/confidence_level["\s:]+(\d+)/i);
    if (confidenceMatch) {
        html += `<div class="analysis-section"><p><strong>Confidence:</strong> ${confidenceMatch[1]}%</p></div>`;
    }

    // Clean up and display a summary
    // Remove JSON syntax noise and show readable text
    let cleanText = output
        .replace(/[{}\[\]"]/g, ' ')  // Remove JSON brackets/quotes
        .replace(/,\s*\n/g, '\n')    // Clean up commas
        .replace(/:\s+/g, ': ')      // Normalize colons
        .replace(/\s+/g, ' ')        // Collapse whitespace
        .replace(/_/g, ' ')          // Replace underscores with spaces
        .trim();

    // Truncate if too long
    if (cleanText.length > 800) {
        cleanText = cleanText.substring(0, 800) + '...';
    }

    html += `<div class="analysis-section">
        <h5>Analysis Summary</h5>
        <p style="font-size: 0.85em; color: #94a3b8; line-height: 1.5;">${cleanText}</p>
    </div>`;

    html += '</div>';
    return html;
}

function formatExecutiveAnalysis(data, role) {
    // Role-specific formatting
    switch(role) {
        case 'cfo':
            return formatCFOOutput(data);
        case 'cpo':
            return formatCPOOutput(data);
        case 'cto':
            return formatCTOOutput(data);
        case 'cro':
            return formatCROOutput(data);
        default:
            return formatGenericOutput(data);
    }
}

function formatCFOOutput(data) {
    let html = '<div class="exec-analysis cfo-analysis">';

    // Recommendation with badge
    if (data.financial_recommendation) {
        html += `<div class="recommendation-row">
            <span class="rec-badge ${getRecClass(data.financial_recommendation)}">
                ${data.financial_recommendation.toUpperCase()}
            </span>
            ${data.confidence_level ? `<span class="confidence">${data.confidence_level}% confident</span>` : ''}
        </div>`;
    }

    // ROI Analysis
    if (data.roi_analysis) {
        html += `<div class="analysis-section">
            <h5>ROI Analysis</h5>
            <p>${typeof data.roi_analysis === 'object' ? JSON.stringify(data.roi_analysis) : data.roi_analysis}</p>
        </div>`;
    }

    // Key Metrics
    if (data.key_metrics) {
        html += '<div class="analysis-section"><h5>Key Metrics</h5>';
        html += formatMetrics(data.key_metrics);
        html += '</div>';
    }

    // Budget Required
    if (data.budget_required) {
        html += `<div class="analysis-section">
            <h5>Budget Required</h5>
            <p>${data.budget_required}</p>
        </div>`;
    }

    // Cost Risks
    if (data.cost_risks && data.cost_risks.length > 0) {
        html += '<div class="analysis-section risks"><h5>Cost Risks</h5><ul>';
        (Array.isArray(data.cost_risks) ? data.cost_risks : [data.cost_risks]).forEach(r => {
            html += `<li class="risk-item">${r}</li>`;
        });
        html += '</ul></div>';
    }

    html += '</div>';
    return html;
}

function formatCPOOutput(data) {
    let html = '<div class="exec-analysis cpo-analysis">';

    // Recommendation
    if (data.product_recommendation) {
        html += `<div class="recommendation-row">
            <span class="rec-badge ${getRecClass(data.product_recommendation)}">
                ${data.product_recommendation.toUpperCase()}
            </span>
            ${data.confidence_level ? `<span class="confidence">${data.confidence_level}% confident</span>` : ''}
        </div>`;
    }

    // Market Demand
    if (data.market_demand) {
        html += `<div class="analysis-section">
            <h5>Market Demand</h5>
            <span class="demand-badge ${String(data.market_demand).toLowerCase()}">${data.market_demand}</span>
        </div>`;
    }

    // Customer Feedback
    if (data.customer_feedback) {
        html += `<div class="analysis-section">
            <h5>Customer Feedback</h5>
            <p>${Array.isArray(data.customer_feedback) ? data.customer_feedback.join(', ') : data.customer_feedback}</p>
        </div>`;
    }

    // Product Roadmap Fit
    if (data.product_roadmap_fit) {
        html += `<div class="analysis-section">
            <h5>Roadmap Fit</h5>
            <span class="fit-badge">${data.product_roadmap_fit}</span>
        </div>`;
    }

    // Competitive Positioning
    if (data.competitive_positioning) {
        html += `<div class="analysis-section">
            <h5>Competitive Positioning</h5>
            <p>${data.competitive_positioning}</p>
        </div>`;
    }

    html += '</div>';
    return html;
}

function formatCTOOutput(data) {
    let html = '<div class="exec-analysis cto-analysis">';

    // Recommendation
    if (data.technology_recommendation) {
        html += `<div class="recommendation-row">
            <span class="rec-badge ${getRecClass(data.technology_recommendation)}">
                ${data.technology_recommendation.toUpperCase()}
            </span>
            ${data.confidence_level ? `<span class="confidence">${data.confidence_level}% confident</span>` : ''}
        </div>`;
    }

    // Technical Feasibility
    if (data.technical_feasibility) {
        html += `<div class="analysis-section">
            <h5>Technical Feasibility</h5>
            <span class="feasibility-badge ${String(data.technical_feasibility).toLowerCase()}">${data.technical_feasibility}</span>
        </div>`;
    }

    // Implementation Timeline
    if (data.implementation_timeline) {
        html += `<div class="analysis-section">
            <h5>Timeline</h5>
            <p>${typeof data.implementation_timeline === 'object' ?
                `MVP: ${data.implementation_timeline.mvp || 'TBD'} | Production: ${data.implementation_timeline.production || 'TBD'}` :
                data.implementation_timeline}</p>
        </div>`;
    }

    // Engineering Effort
    if (data.engineering_effort) {
        html += `<div class="analysis-section">
            <h5>Engineering Effort</h5>
            <p>${data.engineering_effort}</p>
        </div>`;
    }

    // Technical Risks
    if (data.technical_risks && data.technical_risks.length > 0) {
        html += '<div class="analysis-section risks"><h5>Technical Risks</h5><ul>';
        (Array.isArray(data.technical_risks) ? data.technical_risks : [data.technical_risks]).forEach(r => {
            html += `<li class="risk-item">${typeof r === 'object' ? r.risk || JSON.stringify(r) : r}</li>`;
        });
        html += '</ul></div>';
    }

    html += '</div>';
    return html;
}

function formatCROOutput(data) {
    let html = '<div class="exec-analysis cro-analysis">';

    // Recommendation
    if (data.revenue_recommendation) {
        html += `<div class="recommendation-row">
            <span class="rec-badge ${getRecClass(data.revenue_recommendation)}">
                ${data.revenue_recommendation.toUpperCase()}
            </span>
            ${data.confidence_level ? `<span class="confidence">${data.confidence_level}% confident</span>` : ''}
        </div>`;
    }

    // Sales Impact
    if (data.sales_impact) {
        html += `<div class="analysis-section">
            <h5>Sales Impact</h5>
            <span class="impact-badge ${String(data.sales_impact).toLowerCase()}">${data.sales_impact}</span>
        </div>`;
    }

    // Competitive Positioning
    if (data.competitive_positioning_vs_rivals) {
        html += `<div class="analysis-section">
            <h5>Competitive Positioning</h5>
            <p>${data.competitive_positioning_vs_rivals}</p>
        </div>`;
    }

    // Pricing Opportunity
    if (data.pricing_opportunity) {
        html += `<div class="analysis-section">
            <h5>Pricing Opportunity</h5>
            <p>${data.pricing_opportunity}</p>
        </div>`;
    }

    // Deal Acceleration
    if (data.deal_acceleration_potential) {
        html += `<div class="analysis-section">
            <h5>Deal Acceleration</h5>
            <p>${data.deal_acceleration_potential}</p>
        </div>`;
    }

    html += '</div>';
    return html;
}

function formatGenericOutput(data) {
    return `<pre style="white-space: pre-wrap; font-size: 0.85em;">${JSON.stringify(data, null, 2)}</pre>`;
}

function formatMetrics(metrics) {
    if (typeof metrics !== 'object') return `<p>${metrics}</p>`;

    let html = '<div class="metrics-grid">';
    for (const [key, value] of Object.entries(metrics)) {
        html += `<div class="metric-item">
            <span class="metric-label">${key.replace(/_/g, ' ')}</span>
            <span class="metric-value">${value}</span>
        </div>`;
    }
    html += '</div>';
    return html;
}

function getRecClass(rec) {
    const r = String(rec).toLowerCase();
    if (['go', 'proceed', 'build', 'accelerates', 'accelerate'].includes(r)) return 'rec-go';
    if (['pivot', 'proceed_with_caution', 'go_with_changes', 'build_with_constraints', 'neutral'].includes(r)) return 'rec-pivot';
    return 'rec-hold';
}

// ============================================================================
// Comparison View
// ============================================================================

function toggleComparisonView() {
    isComparisonView = !isComparisonView;
    const gridView = document.getElementById('executivesGrid');
    const comparisonView = document.getElementById('comparisonView');
    const toggleBtn = document.getElementById('viewToggle');

    if (isComparisonView) {
        gridView.style.display = 'none';
        comparisonView.style.display = 'block';
        toggleBtn.textContent = 'Show Cards';
        renderComparisonTable();
    } else {
        gridView.style.display = 'grid';
        comparisonView.style.display = 'none';
        toggleBtn.textContent = 'Show Comparison';
    }
}

function renderComparisonTable() {
    const tbody = document.getElementById('comparisonBody');
    if (!tbody) return;

    // Define comparison categories
    const categories = [
        {
            label: 'Recommendation',
            keys: {
                cfo: 'financial_recommendation',
                cpo: 'product_recommendation',
                cto: 'technology_recommendation',
                cro: 'revenue_recommendation'
            }
        },
        {
            label: 'Confidence',
            keys: { cfo: 'confidence_level', cpo: 'confidence_level', cto: 'confidence_level', cro: 'confidence_level' }
        },
        {
            label: 'Key Concern',
            keys: {
                cfo: 'cost_risks',
                cpo: 'market_demand',
                cto: 'technical_risks',
                cro: 'sales_impact'
            }
        },
        {
            label: 'Timeline/Effort',
            keys: {
                cfo: 'budget_required',
                cpo: 'product_roadmap_fit',
                cto: 'implementation_timeline',
                cro: 'deal_acceleration_potential'
            }
        }
    ];

    let html = '';
    categories.forEach(cat => {
        html += '<tr>';
        html += `<td class="category-label">${cat.label}</td>`;

        ['cfo', 'cpo', 'cto', 'cro'].forEach(role => {
            const data = executiveData[role];
            const key = cat.keys[role];
            let value = data && data[key] ? formatComparisonValue(data[key]) : '-';

            // Add visual alignment indicator for recommendations
            if (cat.label === 'Recommendation' && value !== '-') {
                const recClass = getRecClass(value);
                value = `<span class="comparison-rec ${recClass}">${value}</span>`;
            }
            if (cat.label === 'Confidence' && value !== '-') {
                value = `${value}%`;
            }

            html += `<td>${value}</td>`;
        });

        html += '</tr>';
    });

    tbody.innerHTML = html;
}

function formatComparisonValue(value) {
    if (Array.isArray(value)) {
        return value.length > 0 ? (typeof value[0] === 'string' ? value[0].substring(0, 50) : String(value[0]).substring(0, 50)) : '-';
    }
    if (typeof value === 'object' && value !== null) {
        const firstVal = Object.values(value)[0];
        return firstVal ? String(firstVal).substring(0, 50) : '-';
    }
    return String(value).substring(0, 50);
}

function updateConsensus(consensus) {
    const level = consensus.overall_consensus_level;
    const percentage = Math.round(level * 100);

    consensusBar.style.width = `${percentage}%`;
    consensusText.textContent = `${percentage}% Agreement`;

    // Color coding
    if (level > 0.75) {
        consensusBar.style.background = 'linear-gradient(90deg, #10b981, #34d399)';
    } else if (level > 0.5) {
        consensusBar.style.background = 'linear-gradient(90deg, #f97316, #fb923c)';
    } else {
        consensusBar.style.background = 'linear-gradient(90deg, #ef4444, #f87171)';
    }
}

function showFinalDecision(decision) {
    debateInProgress = false;
    startButton.disabled = false;
    showStatus('Debate complete!', 'success');

    decisionPanel.style.display = 'block';

    // Parse decision
    let decisionData;
    try {
        decisionData = typeof decision === 'string' ? JSON.parse(decision.output) : decision;
    } catch {
        decisionData = decision;
    }

    // Update recommendation badge
    const recType = (decisionData.recommendation || 'HOLD').toUpperCase();
    recommendationBadge.className = `recommendation-badge ${recType.toLowerCase()}`;
    recommendationBadge.textContent = `${recType}\n${decisionData.confidence_level || 0}%`;

    // Update decision output
    const summary = decisionData.executive_summary || decisionData.summary || 'Decision pending';
    const nextSteps = decisionData.recommended_next_steps || [];

    let output = `<p><strong>Executive Summary:</strong></p><p>${summary}</p>`;

    if (nextSteps.length > 0) {
        output += '<p><strong>Recommended Next Steps:</strong></p><ul>';
        nextSteps.forEach(step => {
            output += `<li>${step}</li>`;
        });
        output += '</ul>';
    }

    decisionOutput.innerHTML = output;

    // Scroll to decision panel
    decisionPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============================================================================
// Council UI Functions
// ============================================================================

function initializeCouncilUI(providers) {
    const grid = document.getElementById('councilResponses');
    if (!grid) return;

    grid.innerHTML = '';
    councilData = {};

    providers.forEach((providerId, index) => {
        councilData[providerId] = { response: '', complete: false, scores: {} };
        const card = createCouncilCard(providerId, `LLM ${index + 1}`);
        grid.appendChild(card);
    });
}

function createCouncilCard(providerId, label) {
    const card = document.createElement('div');
    card.className = 'council-card';
    card.id = `council-${providerId}`;
    card.innerHTML = `
        <div class="council-header">
            <span class="council-label">${label}</span>
            <span class="council-status">Thinking...</span>
        </div>
        <div class="council-output" id="council-output-${providerId}">
            <span class="waiting">Generating response...</span>
        </div>
        <div class="peer-scores" id="scores-${providerId}"></div>
    `;
    return card;
}

function updateCouncilResponse(providerId, token, streaming) {
    const outputElement = document.getElementById(`council-output-${providerId}`);
    if (!outputElement) return;

    // Clear waiting message on first token
    if (outputElement.textContent.includes('Generating response...')) {
        outputElement.innerHTML = '';
    }

    // Append token
    outputElement.textContent += token;
    outputElement.scrollTop = outputElement.scrollHeight;
}

function completeCouncilResponse(providerId, response, parsedData) {
    const card = document.getElementById(`council-${providerId}`);
    const statusEl = card?.querySelector('.council-status');

    if (statusEl) {
        statusEl.textContent = 'Complete';
        statusEl.classList.add('complete');
    }

    if (councilData[providerId]) {
        councilData[providerId].response = response;
        councilData[providerId].complete = true;
        councilData[providerId].parsed = parsedData;
    }
}

function updateCouncilStage(stage) {
    councilStage = stage;

    // Update stage indicators
    const stages = ['divergence', 'convergence', 'synthesis'];
    const stageIds = ['stageDivergence', 'stageConvergence', 'stageSynthesis'];

    const currentIndex = stages.indexOf(stage);

    stageIds.forEach((id, i) => {
        const el = document.getElementById(id);
        if (!el) return;

        el.classList.remove('active', 'complete');
        if (i < currentIndex) {
            el.classList.add('complete');
        } else if (i === currentIndex) {
            el.classList.add('active');
        }
    });
}

function updatePeerReview(reviewerId, targetId, score) {
    const scoresEl = document.getElementById(`scores-${targetId}`);
    if (!scoresEl) return;

    // Add or update score display
    let scoreItem = scoresEl.querySelector(`[data-reviewer="${reviewerId}"]`);
    if (!scoreItem) {
        scoreItem = document.createElement('div');
        scoreItem.className = 'peer-score-item';
        scoreItem.dataset.reviewer = reviewerId;
        scoresEl.appendChild(scoreItem);
    }

    const scoreClass = score >= 7 ? 'high' : score >= 4 ? 'medium' : 'low';
    scoreItem.innerHTML = `<span class="reviewer">${reviewerId}:</span> <span class="score ${scoreClass}">${score}/10</span>`;

    // Store in councilData
    if (councilData[targetId]) {
        councilData[targetId].scores[reviewerId] = score;
    }
}

function renderRatingMatrix(matrix) {
    const container = document.getElementById('ratingMatrixContainer');
    const matrixEl = document.getElementById('ratingMatrix');
    if (!container || !matrixEl) return;

    container.style.display = 'block';

    const providers = Object.keys(matrix.aggregated_scores);

    let html = '<table class="matrix-table"><thead><tr><th>LLM</th><th>Avg Score</th><th>Rank</th></tr></thead><tbody>';

    // Sort by score
    const sorted = providers
        .map(p => ({ id: p, score: matrix.aggregated_scores[p] }))
        .sort((a, b) => b.score - a.score);

    sorted.forEach((item, i) => {
        const isHighest = item.id === matrix.highest_rated;
        const isLowest = item.id === matrix.lowest_rated;
        const rowClass = isHighest ? 'highest' : isLowest ? 'lowest' : '';
        html += `<tr class="${rowClass}">
            <td>${item.id}</td>
            <td><span class="score-badge">${item.score.toFixed(1)}</span></td>
            <td>#${i + 1}${isHighest ? ' (Chairman)' : ''}</td>
        </tr>`;
    });

    html += '</tbody></table>';
    matrixEl.innerHTML = html;
}

function showCouncilDecision(decision, chairmanProvider) {
    debateInProgress = false;
    startButton.disabled = false;
    showStatus('Council decision complete!', 'success');

    decisionPanel.style.display = 'block';

    // Update recommendation badge
    const recType = (decision.recommendation || 'HOLD').toUpperCase();
    recommendationBadge.className = `recommendation-badge ${recType.toLowerCase()}`;
    recommendationBadge.textContent = `${recType}\n${decision.confidence_level || 0}%`;

    // Update decision output
    let output = `<p><strong>Chairman:</strong> ${chairmanProvider}</p>`;
    output += `<p><strong>Executive Summary:</strong></p><p>${decision.executive_summary || decision.weighted_reasoning || ''}</p>`;

    if (decision.key_insights && decision.key_insights.length > 0) {
        output += '<p><strong>Key Insights from Council:</strong></p><ul>';
        decision.key_insights.forEach(insight => {
            output += `<li>${insight}</li>`;
        });
        output += '</ul>';
    }

    if (decision.next_steps && decision.next_steps.length > 0) {
        output += '<p><strong>Recommended Next Steps:</strong></p><ul>';
        decision.next_steps.forEach(step => {
            output += `<li>${step}</li>`;
        });
        output += '</ul>';
    }

    decisionOutput.innerHTML = output;
    decisionPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showComparisonResults(consensusResult, councilResult, comparison) {
    debateInProgress = false;
    startButton.disabled = false;
    showStatus('Both methods complete!', 'success');

    // Show comparison summary
    const summaryEl = document.getElementById('comparisonSummary');
    if (summaryEl) {
        summaryEl.style.display = 'block';

        // Update metrics
        document.getElementById('matchValue').textContent =
            comparison.recommendations_match ? 'Yes' : 'No';
        document.getElementById('matchValue').className =
            `value ${comparison.recommendations_match ? 'agree' : 'disagree'}`;

        document.getElementById('consensusConfValue').textContent =
            `${comparison.consensus_confidence}%`;
        document.getElementById('councilConfValue').textContent =
            `${comparison.council_confidence}%`;

        // Update insight
        const insightEl = document.getElementById('comparisonInsight');
        if (insightEl) {
            insightEl.innerHTML = `<p>${comparison.combined_insight}</p>`;
            if (comparison.key_differences && comparison.key_differences.length > 0) {
                insightEl.innerHTML += '<p><strong>Key Differences:</strong></p><ul>' +
                    comparison.key_differences.map(d => `<li>${d}</li>`).join('') + '</ul>';
            }
        }
    }

    // Show decision panel with combined result
    decisionPanel.style.display = 'block';

    const consensusRec = comparison.consensus_recommendation;
    const councilRec = comparison.council_recommendation;

    if (comparison.recommendations_match) {
        recommendationBadge.className = `recommendation-badge ${consensusRec.toLowerCase()}`;
        recommendationBadge.textContent = `${consensusRec}\nBoth Agree`;
    } else {
        recommendationBadge.className = 'recommendation-badge mixed';
        recommendationBadge.textContent = `MIXED\n${consensusRec} vs ${councilRec}`;
    }

    decisionOutput.innerHTML = `
        <p><strong>Consensus Method:</strong> ${consensusRec} (${comparison.consensus_confidence}%)</p>
        <p><strong>Council Method:</strong> ${councilRec} (${comparison.council_confidence}%)</p>
        <hr>
        <p>${comparison.combined_insight}</p>
    `;

    decisionPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============================================================================
// Method Selection
// ============================================================================

function updateMethodUI(method) {
    selectedMethod = method;

    // Update button states
    document.querySelectorAll('.method-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.method === method);
    });

    // Update description
    const descriptions = {
        consensus: '4 AI executives debate from their specialized perspectives',
        council: 'Multiple LLMs provide answers, then anonymously peer-review each other',
        both: 'Run both methods in parallel and compare results'
    };
    const descEl = document.getElementById('methodDescription');
    if (descEl) {
        descEl.textContent = descriptions[method] || '';
    }

    // Update cost estimate
    fetchCostEstimate(method);

    // Update view visibility (for when not in debate)
    if (!debateInProgress) {
        const singleView = document.getElementById('singleView');
        const sideBySideView = document.getElementById('sideBySideView');
        const consensusView = document.getElementById('consensusView');
        const councilView = document.getElementById('councilView');

        if (method === 'both') {
            singleView.style.display = 'none';
            sideBySideView.style.display = 'block';
        } else {
            singleView.style.display = 'block';
            sideBySideView.style.display = 'none';
            consensusView.style.display = method === 'consensus' ? 'block' : 'none';
            councilView.style.display = method === 'council' ? 'block' : 'none';
        }
    }
}

async function fetchCostEstimate(method) {
    try {
        const response = await fetch(`/api/cost-estimate/${method}`);
        const data = await response.json();

        const costEl = document.getElementById('costValue');
        if (costEl && data.estimated_cost !== undefined) {
            costEl.textContent = `~$${data.estimated_cost.toFixed(2)}`;
        }
    } catch (error) {
        console.error('Failed to fetch cost estimate:', error);
    }
}

// ============================================================================
// Event Handlers
// ============================================================================

// Method button click handlers
document.querySelectorAll('.method-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        updateMethodUI(e.target.dataset.method);
    });
});

startButton.addEventListener('click', () => {
    const question = questionInput.value.trim();

    if (!question) {
        showStatus('Please enter a question', 'error');
        return;
    }

    // Collect context from individual form fields
    const context = {
        company_size: document.getElementById('companySize').value.trim(),
        current_revenue: document.getElementById('currentRevenue').value.trim(),
        engineering_team: document.getElementById('engineeringTeam').value.trim(),
        market_position: document.getElementById('marketPosition').value.trim(),
        timeline: document.getElementById('timeline').value.trim()
    };

    // Start debate via WebSocket with selected method
    ws.send(JSON.stringify({
        type: 'start_debate',
        question: question,
        context: context,
        method: selectedMethod
    }));
});

function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
}

// ============================================================================
// History Panel Functions
// ============================================================================

let historyPanelOpen = false;
let historyData = [];

function toggleHistoryPanel() {
    const panel = document.getElementById('historyPanel');
    const overlay = document.getElementById('historyOverlay');

    historyPanelOpen = !historyPanelOpen;

    if (historyPanelOpen) {
        panel.classList.add('active');
        overlay.classList.add('active');
        loadHistory();
    } else {
        panel.classList.remove('active');
        overlay.classList.remove('active');
    }
}

async function loadHistory() {
    const listEl = document.getElementById('historyList');
    listEl.innerHTML = '<p class="history-empty">Loading...</p>';

    try {
        const response = await fetch('/api/debates');
        const data = await response.json();

        if (data.debates && data.debates.length > 0) {
            historyData = data.debates;
            renderHistoryList(data.debates);
        } else {
            listEl.innerHTML = '<p class="history-empty">No debates yet. Run your first debate to see it here.</p>';
        }
    } catch (error) {
        console.error('Failed to load history:', error);
        listEl.innerHTML = '<p class="history-empty">Failed to load history. Database may not be configured.</p>';
    }
}

function renderHistoryList(debates) {
    const listEl = document.getElementById('historyList');

    let html = '';
    debates.forEach(debate => {
        const date = new Date(debate.created_at);
        const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const rec = (debate.recommendation || 'PENDING').toUpperCase();
        const recClass = rec === 'GO' ? 'go' : rec === 'PIVOT' ? 'pivot' : 'hold';
        const confidence = debate.confidence || 0;
        const consensus = debate.consensus_level ? Math.round(debate.consensus_level * 100) : 0;

        html += `
            <div class="history-item" onclick="showHistoryDetail('${debate.id}')">
                <div class="history-item-header">
                    <span class="history-item-date">${dateStr}</span>
                    <span class="history-item-rec ${recClass}">${rec}</span>
                </div>
                <div class="history-item-question">${escapeHtml(debate.question)}</div>
                <div class="history-item-meta">
                    <span>🎯 ${confidence}% confidence</span>
                    <span>🤝 ${consensus}% consensus</span>
                </div>
            </div>
        `;
    });

    listEl.innerHTML = html;
}

async function showHistoryDetail(debateId) {
    try {
        const response = await fetch(`/api/debates/${debateId}`);
        const debate = await response.json();

        if (debate.error) {
            alert('Failed to load debate details');
            return;
        }

        // Create and show modal
        showDetailModal(debate);
    } catch (error) {
        console.error('Failed to load debate detail:', error);
        alert('Failed to load debate details');
    }
}

function showDetailModal(debate) {
    // Remove existing modal if any
    const existingModal = document.getElementById('historyDetailModal');
    if (existingModal) existingModal.remove();

    const date = new Date(debate.created_at);
    const dateStr = date.toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    const rec = (debate.recommendation || 'PENDING').toUpperCase();
    const recClass = rec === 'GO' ? 'go' : rec === 'PIVOT' ? 'pivot' : 'hold';

    // Build executives section
    let execsHtml = '';
    const executives = debate.executives || {};
    for (const [role, exec] of Object.entries(executives)) {
        const emoji = exec.emoji || '👤';
        const name = exec.name || role.toUpperCase();
        const title = exec.title || '';

        // Try to extract recommendation from parsed data
        let execRec = '';
        if (exec.parsed_data) {
            const recKey = `${role === 'cfo' ? 'financial' : role === 'cpo' ? 'product' : role === 'cto' ? 'technology' : 'revenue'}_recommendation`;
            execRec = exec.parsed_data[recKey] || '';
        }

        execsHtml += `
            <div class="modal-exec-card">
                <h5>${emoji} ${name} <small style="color: #6B7280; font-weight: normal;">${title}</small></h5>
                ${execRec ? `<div style="margin-bottom: 8px;"><span class="rec-badge ${getRecClass(execRec)}">${execRec.toUpperCase()}</span></div>` : ''}
                <div class="exec-output">${formatExecSummary(exec)}</div>
            </div>
        `;
    }

    // Parse final decision
    let decisionSummary = '';
    let nextSteps = [];
    try {
        const finalDecision = typeof debate.final_decision === 'string'
            ? JSON.parse(debate.final_decision)
            : debate.final_decision;
        if (finalDecision) {
            decisionSummary = finalDecision.executive_summary || finalDecision.summary || '';
            nextSteps = finalDecision.recommended_next_steps || finalDecision.next_steps || [];
        }
    } catch (e) {
        decisionSummary = debate.final_decision || '';
    }

    const modal = document.createElement('div');
    modal.id = 'historyDetailModal';
    modal.className = 'history-detail-modal active';
    modal.innerHTML = `
        <div class="modal-header">
            <h3>${dateStr}</h3>
            <button class="close-btn" onclick="closeDetailModal()">×</button>
        </div>
        <div class="modal-body">
            <div class="modal-section">
                <h4>Question</h4>
                <p>${escapeHtml(debate.question)}</p>
            </div>

            <div class="modal-section">
                <h4>Decision</h4>
                <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px;">
                    <span class="recommendation-badge ${recClass}" style="padding: 12px 20px; font-size: 1.1em;">
                        ${rec}<br><small>${debate.confidence || 0}%</small>
                    </span>
                    <div>
                        <div style="color: #6B7280; font-size: 0.9em;">Consensus Level</div>
                        <div style="font-size: 1.2em; font-weight: 600;">${debate.consensus_level ? Math.round(debate.consensus_level * 100) : 0}%</div>
                    </div>
                </div>
                ${decisionSummary ? `<p>${escapeHtml(decisionSummary)}</p>` : ''}
            </div>

            ${nextSteps.length > 0 ? `
                <div class="modal-section">
                    <h4>Next Steps</h4>
                    <ul style="margin: 0; padding-left: 20px;">
                        ${nextSteps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}

            ${execsHtml ? `
                <div class="modal-section">
                    <h4>Executive Perspectives</h4>
                    <div class="modal-executives-grid">
                        ${execsHtml}
                    </div>
                </div>
            ` : ''}
        </div>
    `;

    document.body.appendChild(modal);

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeDetailModal();
    });
}

function closeDetailModal() {
    const modal = document.getElementById('historyDetailModal');
    if (modal) modal.remove();
}

function formatExecSummary(exec) {
    if (!exec.parsed_data) {
        // Show truncated raw output
        const output = exec.output || '';
        return escapeHtml(output.substring(0, 200) + (output.length > 200 ? '...' : ''));
    }

    const data = exec.parsed_data;
    let summary = [];

    // Extract key insights based on available fields
    if (data.roi_analysis) summary.push(`ROI: ${typeof data.roi_analysis === 'object' ? JSON.stringify(data.roi_analysis) : data.roi_analysis}`);
    if (data.market_demand) summary.push(`Market Demand: ${data.market_demand}`);
    if (data.technical_feasibility) summary.push(`Feasibility: ${data.technical_feasibility}`);
    if (data.sales_impact) summary.push(`Sales Impact: ${data.sales_impact}`);
    if (data.confidence_level) summary.push(`Confidence: ${data.confidence_level}%`);

    if (summary.length === 0) {
        return escapeHtml(JSON.stringify(data).substring(0, 200) + '...');
    }

    return summary.map(s => escapeHtml(s)).join('<br>');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Pre-fill question with default
    questionInput.value = DEFAULT_QUESTION;

    connectWebSocket();

    // Load history count on startup (optional preview)
    loadHistoryPreview();
});

async function loadHistoryPreview() {
    try {
        const response = await fetch('/api/debates');
        const data = await response.json();
        if (data.count > 0) {
            const historyBtn = document.querySelector('.history-btn');
            if (historyBtn) {
                historyBtn.textContent = `📜 History (${data.count})`;
            }
        }
    } catch (e) {
        // Silently fail - database might not be configured
    }
}
