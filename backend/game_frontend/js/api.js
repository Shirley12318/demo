const API_BASE_URL = 'http://localhost:8000';

class ZhengxinAPI {
    constructor() {
        this.baseURL = API_BASE_URL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API请求错误:', error);
            return { status: 'error', message: '网络请求失败' };
        }
    }

    // ========== 认证相关（main.py） ==========
    async register(username, password, identity = '普通学生', age_group = '20-25岁', current_major = '计算机科学') {
        return this.request('/register', {
            method: 'POST',
            body: JSON.stringify({ username, password, identity, age_group, current_major }),
        });
    }

    async login(username, password) {
        return this.request('/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
    }

    // ========== 问答与会话（main.py） ==========
    async askQuestion(username, message, conversationId = null) {
        const body = { username, message };
        if (conversationId) body.conversation_id = conversationId;
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    }

    async getChatHistory(username, limit = 50, offset = 0) {
        return this.request(`/chat/history?username=${encodeURIComponent(username)}&limit=${limit}&offset=${offset}`);
    }

    async getConversations(username) {
        return this.request(`/conversations?username=${encodeURIComponent(username)}`);
    }

    async createConversation(username, title = null) {
        return this.request('/conversations', {
            method: 'POST',
            body: JSON.stringify({ username, title }),
        });
    }

    async getConversationMessages(conversationId, username) {
        return this.request(`/conversations/${conversationId}/messages?username=${encodeURIComponent(username)}`);
    }

    // ========== 讨论区（main.py） ==========
    async getDiscussionTopics() {
        return this.request('/discussion/topics');
    }

    async getDiscussionPosts(topic, username = null, limit = 50, offset = 0) {
        let url = `/discussion/posts?topic=${encodeURIComponent(topic)}&limit=${limit}&offset=${offset}`;
        if (username) url += `&username=${encodeURIComponent(username)}`;
        return this.request(url);
    }

    async createDiscussionPost(username, topic, title, content) {
        return this.request('/discussion/posts', {
            method: 'POST',
            body: JSON.stringify({ username, topic, title, content }),
        });
    }

    async toggleLike(postId, username) {
        return this.request(`/discussion/posts/${postId}/like`, {
            method: 'POST',
            body: JSON.stringify({ username }),
        });
    }

    async reportPost(postId, username, reason = '违规内容') {
        return this.request(`/discussion/posts/${postId}/report`, {
            method: 'POST',
            body: JSON.stringify({ username, reason }),
        });
    }

    // ========== 新闻（main.py） ==========
    async getDailyNews(limit = 6) {
        return this.request(`/news/daily?limit=${limit}`);
    }

    async getRecommendedNews(username, limit = 6) {
        return this.request(`/news/recommended?username=${encodeURIComponent(username)}&limit=${limit}`);
    }

    // ========== 用户管理 ==========
    getCurrentUser() {
        return JSON.parse(localStorage.getItem('zhengxin_user') || 'null');
    }

    setCurrentUser(user) {
        if (user) {
            localStorage.setItem('zhengxin_user', JSON.stringify(user));
        } else {
            this.logout();
        }
    }

    logout() {
        localStorage.removeItem('zhengxin_user');
    }
}

window.ZhengxinAPI = ZhengxinAPI;
