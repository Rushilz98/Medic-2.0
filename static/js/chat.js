document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-btn');
    const resultsContainer = document.getElementById('results-container');
    const symptomsList = document.getElementById('symptoms-list');
    const predictionsList = document.getElementById('predictions-list');
    const newAssessmentBtn = document.getElementById('new-assessment');

    // Function to add message to chat
    function addMessage(message, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message mb-3 ${isUser ? 'user' : 'system'}`;
        
        messageDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="avatar ${isUser ? 'bg-dark' : 'bg-primary text-white'} rounded-circle d-flex align-items-center justify-content-center me-2 me-lg-3" 
                     style="width: 36px; height: 36px; font-size: 0.9rem;">
                    <i class="fas ${isUser ? 'fa-user' : 'fa-heartbeat'}"></i>
                </div>
                <div class="message ${isUser ? 'bg-primary text-white' : 'bg-white border'} rounded p-2 p-lg-3">
                    <p class="mb-0">${message}</p>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Function to show loading indicator
    function showLoading() {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-indicator';
        loadingDiv.className = 'chat-message mb-3 system';
        loadingDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 me-lg-3" 
                     style="width: 36px; height: 36px; font-size: 0.9rem;">
                    <div class="spinner-border spinner-border-sm text-white" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
                <div class="message bg-white border rounded p-2 p-lg-3">
                    <p class="mb-0">Analyzing your symptoms<span class="loading-dots"></span></p>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(loadingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Function to remove loading indicator
    function removeLoading() {
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
    }

    // Function to display results
    function displayResults(data) {
        // Clear previous results
        symptomsList.innerHTML = '';
        predictionsList.innerHTML = '';
        
        // Display detected symptoms
        if (data.symptoms && data.symptoms.length > 0) {
            data.symptoms.forEach(symptom => {
                const tag = document.createElement('span');
                tag.className = 'symptom-tag';
                tag.innerHTML = `<i class="fas fa-tag me-1"></i> ${symptom}`;
                symptomsList.appendChild(tag);
            });
        } else {
            symptomsList.innerHTML = '<p class="text-muted">No symptoms detected from your description.</p>';
        }
        
        // Display predictions
        if (data.predictions && data.predictions.length > 0) {
            data.predictions.forEach((prediction, index) => {
                const card = document.createElement('div');
                card.className = `condition-card p-2 p-lg-3 mb-2 mb-lg-3 ${prediction.is_critical ? 'critical' : ''}`;
                
                // Format confidence as percentage
                const confidencePercent = (prediction.confidence * 100).toFixed(1);
                
                // Create confidence bar
                const confidenceBar = `
                    <div class="confidence-bar mt-1 mt-lg-2">
                        <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                    </div>
                    <small class="text-muted d-block mt-1">${confidencePercent}% confidence</small>
                `;
                
                // Add critical badge if needed
                const criticalBadge = prediction.is_critical ? 
                    `<span class="critical-badge ms-1"><i class="fas fa-exclamation-triangle me-1"></i> CRITICAL</span>` : '';
                
                card.innerHTML = `
                    <div class="d-flex flex-column flex-md-row justify-content-between align-items-start">
                        <h5 class="mb-1">${prediction.disease}${criticalBadge}</h5>
                        <span class="badge bg-${prediction.is_critical ? 'danger' : 'primary'} rounded-pill mt-1 mt-md-0">
                            #${index + 1}
                        </span>
                    </div>
                    ${confidenceBar}
                    ${prediction.is_critical ? 
                      `<div class="alert alert-danger mt-1 mt-lg-2 mb-0 py-1 small">
                          <i class="fas fa-exclamation-circle me-1"></i> 
                          This condition requires immediate medical attention
                      </div>` : ''}
                `;
                
                predictionsList.appendChild(card);
            });
        } else {
            predictionsList.innerHTML = '<p class="text-muted">No potential conditions could be identified. Please try describing your symptoms differently.</p>';
        }
        
        // Show results container
        resultsContainer.style.display = 'block';
        
        // Scroll to results
        setTimeout(() => {
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    // Function to handle sending user message
    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addMessage(message, true);
        userInput.value = '';
        
        // Show loading indicator
        showLoading();
        
        // Send to backend for symptom mapping
        fetch('/api/map_symptoms', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symptoms: message })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            removeLoading();
            
            if (data.error) {
                addMessage(`I encountered an error processing your symptoms: ${data.error}. Please try again or describe your symptoms differently.`);
                return;
            }
            
            if (data.symptoms && data.symptoms.length > 0) {
                addMessage(`I've identified the following symptoms from your description. Would you like me to analyze these for potential conditions?`);
                
                // Show symptoms in a formatted way
                let symptomsText = '<div class="mt-2 mt-lg-2">';
                data.symptoms.forEach(symptom => {
                    symptomsText += `<div class="symptom-item p-2 mb-2 bg-light rounded d-flex align-items-center">
                                        <i class="fas fa-check-circle text-success me-2"></i> 
                                        ${symptom}
                                      </div>`;
                });
                symptomsText += '</div>';
                
                const messageDiv = document.createElement('div');
                messageDiv.className = 'chat-message mb-3 system';
                messageDiv.innerHTML = `
                    <div class="d-flex align-items-start">
                        <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 me-lg-3" 
                             style="width: 36px; height: 36px; font-size: 0.9rem;">
                            <i class="fas fa-heartbeat"></i>
                        </div>
                        <div class="message bg-white border rounded p-2 p-lg-3">
                            <p class="mb-2 fw-bold">Detected Symptoms:</p>
                            ${symptomsText}
                            <div class="mt-2 mt-lg-3 d-flex flex-column flex-sm-row gap-2">
                                <button class="analyze-btn btn btn-primary btn-sm w-100">
                                    <i class="fas fa-stethoscope me-1"></i> Analyze Conditions
                                </button>
                                <button class="rephrase-btn btn btn-outline-secondary btn-sm w-100">
                                    <i class="fas fa-redo me-1"></i> Rephrase
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
                
                // Get references to the specific buttons in this message
                const analyzeBtn = messageDiv.querySelector('.analyze-btn');
                const rephraseBtn = messageDiv.querySelector('.rephrase-btn');
                
                // Add event listeners to these specific buttons
                analyzeBtn.addEventListener('click', function() {
                    const btn = this;
                    // Store the current symptoms for this specific analysis
                    const currentSymptoms = data.symptoms;
                    
                    // Show loading state
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Analyzing...';
                    btn.disabled = true;
                    
                    // Send to prediction API with current symptoms
                    fetch('/api/predict', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ symptoms: currentSymptoms })
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Prediction API error');
                        }
                        return response.json();
                    })
                    .then(predictionData => {
                        // Reset button state
                        btn.innerHTML = '<i class="fas fa-stethoscope me-1"></i> Analyze Conditions';
                        btn.disabled = false;
                        
                        // Show results with current symptoms
                        displayResults({
                            symptoms: currentSymptoms,
                            predictions: predictionData.predictions
                        });
                    })
                    .catch(error => {
                        console.error('Prediction error:', error);
                        
                        // Reset button state
                        btn.innerHTML = '<i class="fas fa-stethoscope me-1"></i> Analyze Conditions';
                        btn.disabled = false;
                        
                        addMessage('I encountered an error analyzing potential conditions. Please try again later.');
                    });
                });
                
                rephraseBtn.addEventListener('click', function() {
                    userInput.focus();
                });
            } else {
                addMessage(`I couldn't identify any specific symptoms from your description. Could you please describe what you're experiencing in more detail? For example: "I've been having chest pain and trouble breathing for the past two days."`);
            }
        })
        .catch(error => {
            removeLoading();
            console.error('Error:', error);
            addMessage('I encountered a network error. Please check your connection and try again.');
        });
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    newAssessmentBtn.addEventListener('click', function() {
        // Clear results
        resultsContainer.style.display = 'none';
        
        // Add separator to chat
        const separator = document.createElement('div');
        separator.className = 'my-3 my-lg-4 text-center';
        separator.innerHTML = '<small class="bg-white px-2 px-lg-3 py-1 rounded shadow-sm text-muted">--- New Assessment Started ---</small>';
        chatContainer.appendChild(separator);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Focus input
        userInput.focus();
        
        // Clear any previous error states
        userInput.classList.remove('is-invalid');
    });
    
    // Initial focus
    userInput.focus();
    
    // Add keyboard shortcut for new assessment
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            newAssessmentBtn.click();
        }
    });
    
    // Mobile keyboard handling
    document.addEventListener('focusin', function(e) {
        if (e.target === userInput) {
            // On mobile, when keyboard appears, scroll to input
            setTimeout(() => {
                const inputRect = userInput.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                
                if (inputRect.bottom > windowHeight * 0.65) {
                    window.scrollTo({
                        top: window.scrollY + inputRect.bottom - windowHeight * 0.6,
                        behavior: 'smooth'
                    });
                }
            }, 300);
        }
    });
    
    // Auto-resize textarea as content grows
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.scrollHeight > 100) {
            this.style.overflowY = 'auto';
        } else {
            this.style.overflowY = 'hidden';
        }
    });
    
    // Handle viewport resizing (for mobile orientation changes)
    let viewportHeight = window.innerHeight;
    window.addEventListener('resize', function() {
        if (Math.abs(window.innerHeight - viewportHeight) > 50) {
            // Significant change in viewport height (likely keyboard appearing/disappearing)
            viewportHeight = window.innerHeight;
            
            // Adjust chat container height
            const inputArea = document.querySelector('.input-area');
            const chatContainer = document.getElementById('chat-container');
            
            if (chatContainer && inputArea) {
                const inputRect = inputArea.getBoundingClientRect();
                chatContainer.style.maxHeight = `calc(100vh - ${inputRect.top + 10}px)`;
            }
        }
    });
});