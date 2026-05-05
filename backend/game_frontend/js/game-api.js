const API_BASE_URL = 'http://localhost:5000/api';

class GameAPI {
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

            if (!response.ok) {
                throw new Error(data.error || '请求失败');
            }

            return data;
        } catch (error) {
            console.error('API请求错误:', error);
            throw error;
        }
    }

    async createPlayer(name) {
        return this.request('/player/create', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async getPlayer(playerId) {
        return this.request(`/player/${playerId}`);
    }

    async updatePlayer(playerId, data) {
        return this.request(`/player/${playerId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    async deletePlayer(playerId) {
        return this.request(`/player/${playerId}`, {
            method: 'DELETE',
        });
    }

    async getPlayers() {
        return this.request('/players');
    }

    async rollDice(special = false) {
        return this.request('/game/roll', {
            method: 'POST',
            body: JSON.stringify({ special }),
        });
    }

    async getBoard() {
        return this.request('/game/board');
    }

    async movePlayer(playerId, diceValue) {
        return this.request(`/game/move/${playerId}`, {
            method: 'POST',
            body: JSON.stringify({ dice_value: diceValue }),
        });
    }

    async resetGame(playerId, resetAll = false) {
        return this.request(`/game/reset/${playerId}`, {
            method: 'POST',
            body: JSON.stringify({ reset_all: resetAll }),
        });
    }

    async getCellInfo(position) {
        return this.request(`/game/cell/${position}`);
    }

    async getRandomQuestions(difficulty = null, category = null, count = 1) {
        let url = `/question/random?count=${count}`;
        if (difficulty) url += `&difficulty=${difficulty}`;
        if (category) url += `&category=${category}`;
        return this.request(url);
    }

    async getQuestionsByCategory(category) {
        return this.request(`/question/category/${category}`);
    }

    async submitAnswer(playerId, questionId, answer) {
        return this.request('/question/answer', {
            method: 'POST',
            body: JSON.stringify({
                player_id: playerId,
                question_id: questionId,
                answer,
            }),
        });
    }

    async getAllQuestions() {
        return this.request('/questions');
    }

    async getEvent(eventId, playerId = null) {
        let url = `/story/event/${eventId}`;
        if (playerId) url += `?player_id=${playerId}`;
        return this.request(url);
    }

    async makeChoice(playerId, eventId, choiceIndex) {
        return this.request('/story/choice', {
            method: 'POST',
            body: JSON.stringify({
                player_id: playerId,
                event_id: eventId,
                choice_index: choiceIndex,
            }),
        });
    }

    async getProgress(playerId) {
        return this.request(`/story/progress/${playerId}`);
    }

    async getAllEvents() {
        return this.request('/story/events');
    }

    async getLocations() {
        return this.request('/locations');
    }

    async getLocation(locationId) {
        return this.request(`/location/${locationId}`);
    }
}

window.GameAPI = GameAPI;
