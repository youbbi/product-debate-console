// WebSocket connection
let ws = null;
let debateInProgress = false;
let executiveData = {};  // Store parsed data for comparison view
let executivePhases = {};  // Track phase state per exec: { cfo: { phase, timeline: [], inputSummary } }
let isComparisonView = false;

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
            initializeDebateUI();
            showStatus('Debate starting... Execs are thinking...', 'loading');
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
    }
}

// ============================================================================
// UI Updates
// ============================================================================

function initializeDebateUI() {
    debateInProgress = true;
    startButton.disabled = true;
    executivesGrid.innerHTML = '';
    decisionPanel.style.display = 'none';
    executiveData = {};  // Reset stored data
    executivePhases = {};  // Reset phase tracking

    // Reset comparison view
    const comparisonBody = document.getElementById('comparisonBody');
    if (comparisonBody) {
        comparisonBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;">Waiting for executive analysis...</td></tr>';
    }

    // Create executive cards
    EXECUTIVES.forEach(exec => {
        const card = createExecutiveCard(exec);
        executivesGrid.appendChild(card);
    });
}

function createExecutiveCard(exec) {
    const card = document.createElement('div');
    card.className = 'executive-card';
    card.id = `exec-${exec.role}`;
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
            // If not JSON, display as-is
            displayContent = `<pre style="white-space: pre-wrap; font-size: 0.9em;">${fullOutput}</pre>`;
        }

        outputElement.innerHTML = displayContent;
        outputElement.parentElement.scrollTop = 0;
    }
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
// Event Handlers
// ============================================================================

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

    // Start debate via WebSocket
    ws.send(JSON.stringify({
        type: 'start_debate',
        question: question,
        context: context
    }));
});

function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
}

// ============================================================================
// Initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Pre-fill question with default
    questionInput.value = DEFAULT_QUESTION;

    connectWebSocket();
});
