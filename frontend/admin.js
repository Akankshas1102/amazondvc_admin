const AdminPanel = {
    API_BASE: 'http://127.0.0.1:7070/api/admin',
    token: null,
    username: null,
    isAdmin: false,
    currentQuery: null,
    queryMode: 'basic', // 'basic' or 'advanced'
    
    init() {
        // Check authentication
        this.token = localStorage.getItem('adminToken');
        this.username = localStorage.getItem('adminUsername');
        this.isAdmin = localStorage.getItem('isAdmin') === 'true';
        
        console.log('[Admin] Initialization:', {
            hasToken: !!this.token,
            username: this.username,
            isAdmin: this.isAdmin
        });
        
        if (!this.token) {
            // Not logged in, redirect to login
            window.location.href = '/login';
            return;
        }

        // Check if user is admin
        if (!this.isAdmin) {
            this.showNotification('Admin privileges required. Redirecting to main app...', 'error');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
            return;
        }
        
        // Display username
        document.getElementById('username').textContent = this.username || 'Admin';
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial data
        this.loadQueries();
        this.loadUsers();
    },
    
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
        
        // Query mode buttons
        document.getElementById('basicModeBtn').addEventListener('click', () => this.switchQueryMode('basic'));
        document.getElementById('advancedModeBtn').addEventListener('click', () => this.switchQueryMode('advanced'));
        
        // Change password form
        document.getElementById('changePasswordForm').addEventListener('submit', (e) => this.changePassword(e));
        
        // Create user form
        document.getElementById('createUserForm').addEventListener('submit', (e) => this.createUser(e));
    },
    
    switchTab(tabName) {
        // Update nav tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });

        // Load data if needed
        if (tabName === 'users') {
            this.loadUsers();
        }
    },
    
    switchQueryMode(mode) {
        this.queryMode = mode;
        
        // Update button states
        document.getElementById('basicModeBtn').classList.toggle('active', mode === 'basic');
        document.getElementById('advancedModeBtn').classList.toggle('active', mode === 'advanced');
        
        // Show/hide appropriate forms
        document.getElementById('basicModeForm').style.display = mode === 'basic' ? 'block' : 'none';
        document.getElementById('advancedModeForm').style.display = mode === 'advanced' ? 'block' : 'none';

        // If switching modes with a loaded query, populate the appropriate form
        if (this.currentQuery) {
            if (mode === 'basic') {
                this.populateBasicMode(this.currentQuery.query_sql);
            } else {
                this.populateAdvancedMode(this.currentQuery.query_sql);
            }
        }
    },
    
    populateBasicMode(querySQL) {
        // Extract device type from panel_devices query
        const deviceTypeMatch = querySQL.match(/dvcDeviceType_FRK\s*=\s*(\d+)/i);
        if (deviceTypeMatch) {
            document.getElementById('deviceType').value = deviceTypeMatch[1];
        }
        
        // Extract building table name
        const buildingTableMatch = querySQL.match(/FROM\s+(\w+)/i);
        if (buildingTableMatch) {
            document.getElementById('buildingTableName').value = buildingTableMatch[1];
        }
    },
    
    populateAdvancedMode(querySQL) {
        document.getElementById('querySQL').value = querySQL;
    },
    
    logout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
            localStorage.removeItem('isAdmin');
            window.location.href = '/login';
        }
    },
    
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
                    localStorage.removeItem('isAdmin');
                    window.location.href = '/login';
                }, 2000);
                throw new Error('Unauthorized');
            }
            
            if (response.status === 403) {
                // Not authorized (not admin)
                this.showNotification('Admin privileges required', 'error');
                throw new Error('Forbidden');
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
    
    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 4000);
    },
    
    // ==================== QUERY MANAGEMENT ====================
    
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
            
            // Start in basic mode by default
            this.switchQueryMode('basic');
            this.populateBasicMode(data.query_sql);
            
            // Also populate advanced mode in background
            this.populateAdvancedMode(data.query_sql);
            
            // Highlight active query in list
            document.querySelectorAll('.query-item').forEach(item => {
                item.classList.toggle('active', item.dataset.queryName === queryName);
            });
            
        } catch (error) {
            this.showNotification(`Failed to load query: ${queryName}`, 'error');
        }
    },
    
    async loadDefaultQuery() {
        if (!this.currentQuery) return;
        
        if (!confirm('This will replace the current query with the default. Continue?')) {
            return;
        }
        
        try {
            const data = await this.apiRequest(`queries/${this.currentQuery.query_name}/default`);
            
            if (this.queryMode === 'basic') {
                this.populateBasicMode(data.query_sql);
            } else {
                document.getElementById('querySQL').value = data.query_sql;
            }
            
            document.getElementById('queryDescription').value = data.description || '';
            this.showNotification('Default query loaded', 'info');
        } catch (error) {
            this.showNotification('Failed to load default query', 'error');
        }
    },
    
    async testQuery() {
        if (!this.currentQuery) return;
        
        const querySQL = this.buildQueryFromMode();
        
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
            // Temporarily save to test
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
    
    buildQueryFromMode() {
        if (this.queryMode === 'advanced') {
            return document.getElementById('querySQL').value.trim();
        } else {
            // Build query from basic mode inputs
            const deviceType = document.getElementById('deviceType').value.trim();
            const buildingTable = document.getElementById('buildingTableName').value.trim();
            
            // Get current query SQL as template
            if (!this.currentQuery) return '';
            
            let querySQL = this.currentQuery.query_sql;
            
            // Replace device type if provided
            if (deviceType) {
                querySQL = querySQL.replace(/dvcDeviceType_FRK\s*=\s*\d+/gi, `dvcDeviceType_FRK = ${deviceType}`);
            }
            
            // Replace building table name if provided
            if (buildingTable) {
                // This is more complex - need to handle multiple occurrences
                querySQL = querySQL.replace(/Building_TBL/gi, buildingTable);
            }
            
            return querySQL;
        }
    },
    
    async saveQuery() {
        if (!this.currentQuery) return;
        
        const queryName = document.getElementById('queryName').value;
        const queryDescription = document.getElementById('queryDescription').value.trim();
        const querySQL = this.buildQueryFromMode();
        
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
    
    // ==================== USER MANAGEMENT ====================
    
    async loadUsers() {
        const usersList = document.getElementById('usersList');
        usersList.innerHTML = '<div class="loader">Loading users...</div>';
        
        try {
            const users = await this.apiRequest('users');
            
            usersList.innerHTML = '';
            
            if (users.length === 0) {
                usersList.innerHTML = '<p class="empty-state">No users found</p>';
                return;
            }
            
            users.forEach(user => {
                const userCard = this.createUserCard(user);
                usersList.appendChild(userCard);
            });
            
        } catch (error) {
            usersList.innerHTML = '<p class="error-state">Failed to load users</p>';
            this.showNotification('Failed to load users', 'error');
        }
    },
    
    createUserCard(user) {
        const div = document.createElement('div');
        div.className = 'user-card';
        
        const isCurrentUser = user.username === this.username;
        
        div.innerHTML = `
            <div class="user-card-header">
                <div>
                    <h4 class="user-card-username">
                        ${user.username}
                        ${isCurrentUser ? '<span class="badge" style="background: #3b82f6; color: white;">You</span>' : ''}
                        ${user.is_admin ? '<span class="badge" style="background: #f59e0b; color: white;">Admin</span>' : ''}
                    </h4>
                    <p class="user-card-date">Created: ${new Date(user.created_at).toLocaleDateString()}</p>
                </div>
                <div class="user-card-actions">
                    ${!isCurrentUser ? `
                        <button class="btn btn-secondary btn-sm" onclick="AdminPanel.toggleUserAdmin(${user.id}, ${!user.is_admin})">
                            ${user.is_admin ? 'Remove Admin' : 'Make Admin'}
                        </button>
                        <button class="btn btn-info btn-sm" onclick="AdminPanel.resetUserPassword(${user.id}, '${user.username}')">
                            Reset Password
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="AdminPanel.deleteUser(${user.id}, '${user.username}')">
                            Delete
                        </button>
                    ` : '<span style="color: #64748b; font-size: 0.85rem;">Use "Change Password" tab to update your password</span>'}
                </div>
            </div>
        `;
        
        return div;
    },
    
    async createUser(event) {
        event.preventDefault();
        
        const username = document.getElementById('newUsername').value.trim();
        const password = document.getElementById('newUserPassword').value;
        const isAdmin = document.getElementById('newUserIsAdmin').checked;
        
        if (username.length < 3) {
            this.showNotification('Username must be at least 3 characters', 'error');
            return;
        }
        
        if (password.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest('users', {
                method: 'POST',
                body: JSON.stringify({
                    username: username,
                    password: password,
                    is_admin: isAdmin
                })
            });
            
            this.showNotification(`User '${username}' created successfully!`, 'success');
            
            // Clear form
            document.getElementById('createUserForm').reset();
            
            // Reload users list
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to create user', 'error');
        }
    },
    
    async toggleUserAdmin(userId, makeAdmin) {
        const action = makeAdmin ? 'grant admin privileges to' : 'remove admin privileges from';
        
        if (!confirm(`Are you sure you want to ${action} this user?`)) {
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    is_admin: makeAdmin
                })
            });
            
            this.showNotification('User updated successfully', 'success');
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to update user', 'error');
        }
    },
    
    async resetUserPassword(userId, username) {
        const newPassword = prompt(`Enter new password for user '${username}':\n(Minimum 6 characters)`);
        
        if (!newPassword) return;
        
        if (newPassword.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    new_password: newPassword
                })
            });
            
            this.showNotification(`Password reset successfully for user '${username}'`, 'success');
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to reset password', 'error');
        }
    },
    
    async deleteUser(userId, username) {
        if (!confirm(`Are you sure you want to delete user '${username}'?\n\nThis action cannot be undone.`)) {
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'DELETE'
            });
            
            this.showNotification(`User '${username}' deleted successfully`, 'success');
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to delete user', 'error');
        }
    },
    
    // ==================== PASSWORD CHANGE ====================
    
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