// Main JavaScript for VoteSecure

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all interactive components
    initFlashMessages();
    initFormValidation();
    initVotingSystem();
    initDashboardCharts();
});

// Flash messages auto-dismiss
function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });
}

// Form validation
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            const inputs = form.querySelectorAll('input[required]');
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    showInputError(input, 'This field is required');
                } else {
                    clearInputError(input);
                }
            });
            
            // Email validation
            const emailInput = form.querySelector('input[type="email"]');
            if (emailInput && emailInput.value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(emailInput.value)) {
                    isValid = false;
                    showInputError(emailInput, 'Please enter a valid email address');
                }
            }
            
            if (!isValid) {
                e.preventDefault();
            }
        });
    });
}

function showInputError(input, message) {
    clearInputError(input);
    input.classList.add('error');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'input-error';
    errorDiv.style.color = 'var(--danger)';
    errorDiv.style.fontSize = '0.8rem';
    errorDiv.style.marginTop = '0.25rem';
    errorDiv.textContent = message;
    
    input.parentNode.appendChild(errorDiv);
}

function clearInputError(input) {
    input.classList.remove('error');
    const existingError = input.parentNode.querySelector('.input-error');
    if (existingError) {
        existingError.remove();
    }
}

// Voting system
function initVotingSystem() {
    const voteButtons = document.querySelectorAll('.vote-btn');
    
    voteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const candidateId = this.dataset.candidateId;
            const candidateName = this.dataset.candidateName;
            const electionId = this.dataset.electionId;
            
            if (confirm(`Are you sure you want to vote for ${candidateName}? This action cannot be undone.`)) {
                submitVote(electionId, candidateId);
            }
        });
    });
}

function submitVote(electionId, candidateId) {
    const formData = new FormData();
    formData.append('election_id', electionId);
    formData.append('candidate_id', candidateId);
    
    fetch('/voter/submit-vote', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(() => {
                window.location.href = '/voter/dashboard';
            }, 2000);
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred while submitting your vote', 'error');
    });
}

// Dashboard charts (placeholder for future implementation)
function initDashboardCharts() {
    // This would integrate with Chart.js or similar library
    console.log('Charts initialized');
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button class="notification-close">&times;</button>
    `;
    
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? 'var(--success)' : type === 'error' ? 'var(--danger)' : 'var(--info)'};
        color: white;
        border-radius: 8px;
        box-shadow: var(--shadow);
        z-index: 1000;
        animation: slideInRight 0.3s ease;
        display: flex;
        align-items: center;
        gap: 1rem;
        max-width: 400px;
    `;
    
    document.body.appendChild(notification);
    
    // Close button
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.remove();
    });
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .input-error {
        color: var(--danger);
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    .error {
        border-color: var(--danger) !important;
    }
`;
document.head.appendChild(style);