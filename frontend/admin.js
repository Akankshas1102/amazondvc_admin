// frontend/admin.js
/**
 * Admin Panel Script
 * ==================
 * Handles query configuration and admin settings
 */

const AdminPanel = {
    API_BASE: 'http://127.0.0.1:7070/api/admin',
    token: null,
    username: null,
    currentQuery: null,
    
    /**
     * Initialize the admin panel
     */
    init() {
        // Check authentication
        this.token = localStorage.getItem('adminToken');
        this.username = localStorage.getItem('adminUsername');
        
        if (!this.token) {
            // Not logged in, redirect to login
            window.location.href = '/login';
            return;
        }
        
        // Display username
        document.getElementById('username').textContent = this.username || 'Admin';
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial data
        this.loadQueries();
    },
    
    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Logout button
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());
        
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // Query editor buttons
        document.getElementById('saveQueryBtn').addEventListener('click', () => this.saveQuery());
        document.getElementById('cancelEditBtn').addEventListener('click', () => this.cancelEdit());
        document.getElementById('loadDefaultBtn').addEventListener('click', () => this.loadDefaultQuery());
        document.getElementById('testQueryBtn').addEventListener('click', () => this.testQuery());
        
        // Change password form
        document.getElementById('changePasswordForm').addEventListener('submit', (e) => this.changePassword(e));
    },
    
    /**
     * Switch between tabs
     */
    switchTab(tabName) {
        // Update nav tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });
    },
    
    /**
     * Logout user
     */
    logout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
            window.location.href = '/login';
        }
    },
    
    /**
     * Make authenticated API request
     */
    async apiRequest(endpoint, options = {}) {
        const url = `${this.API_BASE}/${endpoint}`;
        
        const headers = {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        try {
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            if (response.status === 401) {
                // Token expired or invalid
                this.showNotification('Session expired. Please login again.', 'error');
                setTimeout(() => {
                    localStorage.removeItem('adminToken');
                    localStorage.removeItem('adminUsername');
                    window.location.href = '/login';
                }, 2000);
                throw new Error('Unauthorized');
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    },
    
    /**
     * Show notification toast
     */
    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 4000);
    },
    
    /**
     * Load all queries
     */
    async loadQueries() {
        const queryList = document.getElementById('queryList');
        queryList.innerHTML = '<div class="loader">Loading queries...</div>';
        
        try {
            const data = await this.apiRequest('queries');
            
            queryList.innerHTML = '';
            
            if (data.queries.length === 0) {
                queryList.innerHTML = '<p class="empty-state">No queries found</p>';
                return;
            }
            
            data.queries.forEach(query => {
                const queryItem = this.createQueryListItem(query);
                queryList.appendChild(queryItem);
            });
            
        } catch (error) {
            queryList.innerHTML = '<p class="error-state">Failed to load queries</p>';
            this.showNotification('Failed to load queries', 'error');
        }
    },
    
    /**
     * Create query list item element
     */
    createQueryListItem(query) {
        const div = document.createElement('div');
        div.className = 'query-item';
        div.dataset.queryName = query.query_name;
        
        const isDefault = !query.updated_at;
        
        div.innerHTML = `
            <div class="query-item-header">
                <h4>${query.query_name}${isDefault ? ' <span class="badge">Default</span>' : ''}</h4>
                <span class="query-item-date">
                    ${query.updated_at ? `Updated: ${new Date(query.updated_at).toLocaleDateString()}` : 'Not customized'}
                </span>
            </div>
            <p class="query-item-description">${query.description || 'No description'}</p>
        `;
        
        div.addEventListener('click', () => this.loadQueryForEdit(query.query_name));
        
        return div;
    },
    
    /**
     * Load query for editing
     */
    async loadQueryForEdit(queryName) {
        try {
            const data = await this.apiRequest(`queries/${queryName}`);
            
            this.currentQuery = data;
            
            // Hide placeholder, show editor
            document.getElementById('editorPlaceholder').style.display = 'none';
            document.getElementById('queryEditor').style.display = 'block';
            document.getElementById('loadDefaultBtn').style.display = 'inline-block';
            document.getElementById('testQueryBtn').style.display = 'inline-block';
            
            // Populate form
            document.getElementById('editorTitle').textContent = `Editing: ${queryName}`;
            document.getElementById('queryName').value = data.query_name;
            document.getElementById('queryDescription').value = data.description || '';
            document.getElementById('querySQL').value = data.query_sql;
            
            // Highlight active query in list
            document.querySelectorAll('.query-item').forEach(item => {
                item.classList.toggle('active', item.dataset.queryName === queryName);
            });
            
        } catch (error) {
            this.showNotification(`Failed to load query: ${queryName}`, 'error');
        }
    },
    
    /**
     * Load default query
     */
    async loadDefaultQuery() {
        if (!this.currentQuery) return;
        
        if (!confirm('This will replace the current query with the default. Continue?')) {
            return;
        }
        
        try {
            const data = await this.apiRequest(`queries/${this.currentQuery.query_name}/default`);
            document.getElementById('querySQL').value = data.query_sql;
            document.getElementById('queryDescription').value = data.description || '';
            this.showNotification('Default query loaded', 'info');
        } catch (error) {
            this.showNotification('Failed to load default query', 'error');
        }
    },
    
    /**
     * Test/validate query
     */
    async testQuery() {
        if (!this.currentQuery) return;
        
        const querySQL = document.getElementById('querySQL').value.trim();
        
        if (!querySQL) {
            this.showNotification('Query cannot be empty', 'error');
            return;
        }
        
        // Basic client-side validation
        if (!querySQL.toLowerCase().trim().startsWith('select')) {
            this.showNotification('Query must be a SELECT statement', 'error');
            return;
        }
        
        try {
            const response = await this.apiRequest(`queries/${this.currentQuery.query_name}/test`, {
                method: 'POST'
            });
            
            if (response.success) {
                this.showNotification('✅ Query syntax is valid!', 'success');
            } else {
                this.showNotification(`❌ ${response.message}`, 'error');
            }
        } catch (error) {
            this.showNotification('Query validation failed', 'error');
        }
    },
    
    /**
     * Save query
     */
    async saveQuery() {
        if (!this.currentQuery) return;
        
        const queryName = document.getElementById('queryName').value;
        const queryDescription = document.getElementById('queryDescription').value.trim();
        const querySQL = document.getElementById('querySQL').value.trim();
        
        if (!querySQL) {
            this.showNotification('Query cannot be empty', 'error');
            return;
        }
        
        if (!querySQL.toLowerCase().trim().startsWith('select')) {
            this.showNotification('Only SELECT queries are allowed', 'error');
            return;
        }
        
        if (!confirm('Save this query? Changes will take effect immediately.')) {
            return;
        }
        
        try {
            await this.apiRequest('queries', {
                method: 'POST',
                body: JSON.stringify({
                    query_name: queryName,
                    query_sql: querySQL,
                    description: queryDescription
                })
            });
            
            this.showNotification('Query saved successfully!', 'success');
            
            // Reload queries list
            await this.loadQueries();
            
            // Reload current query to show updated timestamp
            await this.loadQueryForEdit(queryName);
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to save query', 'error');
        }
    },
    
    /**
     * Cancel editing
     */
    cancelEdit() {
        if (confirm('Discard changes?')) {
            document.getElementById('queryEditor').style.display = 'none';
            document.getElementById('editorPlaceholder').style.display = 'flex';
            document.getElementById('loadDefaultBtn').style.display = 'none';
            document.getElementById('testQueryBtn').style.display = 'none';
            
            document.querySelectorAll('.query-item').forEach(item => {
                item.classList.remove('active');
            });
            
            this.currentQuery = null;
        }
    },
    
    /**
     * Change password
     */
    async changePassword(event) {
        event.preventDefault();
        
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        // Validate passwords match
        if (newPassword !== confirmPassword) {
            this.showNotification('New passwords do not match', 'error');
            return;
        }
        
        // Validate password length
        if (newPassword.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest('change-password', {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });
            
            this.showNotification('Password changed successfully! Redirecting to login...', 'success');
            
            // Clear form
            document.getElementById('changePasswordForm').reset();
            
            // Logout and redirect after 2 seconds
            setTimeout(() => {
                this.logout();
            }, 2000);
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to change password', 'error');
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    AdminPanel.init();
});