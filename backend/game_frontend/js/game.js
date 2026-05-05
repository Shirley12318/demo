class Game {
    constructor() {
        this.api = new GameAPI();
        this.player = null;
        this.playerId = null;
        this.progress = null;
        this.snake = [];
        this.food = null;
        this.direction = 'right';
        this.nextDirection = 'right';
        this.gameSpeed = 150;
        this.gameLoop = null;
        this.score = 0;
        this.gameState = 'idle';
        this.canvas = null;
        this.ctx = null;
        this.gridSize = 20;
        this.canvasWidth = 800;
        this.canvasHeight = 600;
    }

    async init(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        
        try {
            console.log('游戏初始化成功');
        } catch (error) {
            console.error('游戏初始化失败:', error);
        }
    }

    async createPlayer(name) {
        try {
            const result = await this.api.createPlayer(name);
            this.player = result.player;
            this.playerId = result.player.id;
            this.progress = result.progress;
            this.savePlayerId();
            return result;
        } catch (error) {
            console.error('创建玩家失败:', error);
            throw error;
        }
    }

    async loadPlayer(playerId) {
        try {
            const result = await this.api.getPlayer(playerId);
            this.player = result.player;
            this.playerId = result.player.id;
            this.progress = result.progress || null;
            return result;
        } catch (error) {
            console.error('加载玩家失败:', error);
            throw error;
        }
    }

    async refreshPlayer() {
        if (!this.playerId) return;
        try {
            const result = await this.api.getPlayer(this.playerId);
            this.player = result.player;
            this.progress = result.progress;
            return result;
        } catch (error) {
            console.error('刷新玩家数据失败:', error);
        }
    }

    startGame() {
        this.snake = [
            { x: 10, y: 10 },
            { x: 9, y: 10 },
            { x: 8, y: 10 }
        ];
        this.direction = 'right';
        this.nextDirection = 'right';
        this.score = 0;
        this.generateFood();
        this.gameState = 'playing';
        
        if (this.gameLoop) clearInterval(this.gameLoop);
        this.gameLoop = setInterval(() => this.update(), this.gameSpeed);
    }

    generateFood() {
        const maxX = this.canvasWidth / this.gridSize - 1;
        const maxY = this.canvasHeight / this.gridSize - 1;
        
        do {
            this.food = {
                x: Math.floor(Math.random() * maxX),
                y: Math.floor(Math.random() * maxY)
            };
        } while (this.checkCollision(this.food, this.snake));
    }

    checkCollision(pos, array) {
        return array.some(segment => segment.x === pos.x && segment.y === pos.y);
    }

    update() {
        if (this.gameState !== 'playing') return;
        
        this.direction = this.nextDirection;
        
        const head = { ...this.snake[0] };
        switch (this.direction) {
            case 'up':
                head.y--;
                break;
            case 'down':
                head.y++;
                break;
            case 'left':
                head.x--;
                break;
            case 'right':
                head.x++;
                break;
        }
        
        if (head.x < 0 || head.x >= this.canvasWidth / this.gridSize ||
            head.y < 0 || head.y >= this.canvasHeight / this.gridSize ||
            this.checkCollision(head, this.snake)) {
            this.gameOver();
            return;
        }
        
        this.snake.unshift(head);
        
        if (head.x === this.food.x && head.y === this.food.y) {
            this.score++;
            this.generateFood();
            this.triggerEvent();
        } else {
            this.snake.pop();
        }
        
        this.draw();
    }

    async triggerEvent() {
        try {
            const events = await this.api.getRandomEvents(1);
            if (events && events.length > 0) {
                const event = events[0];
                this.showEventModal(event);
            }
        } catch (error) {
            console.error('触发事件失败:', error);
        }
    }

    showEventModal(event) {
        // 这里需要实现事件模态框的显示逻辑
        console.log('触发事件:', event);
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight);
        
        this.ctx.fillStyle = '#ff6b6b';
        this.snake.forEach(segment => {
            this.ctx.fillRect(
                segment.x * this.gridSize,
                segment.y * this.gridSize,
                this.gridSize - 2,
                this.gridSize - 2
            );
        });
        
        this.ctx.fillStyle = '#ff9f43';
        this.ctx.fillRect(
            this.food.x * this.gridSize,
            this.food.y * this.gridSize,
            this.gridSize - 2,
            this.gridSize - 2
        );
    }

    setDirection(newDirection) {
        if ((newDirection === 'up' && this.direction !== 'down') ||
            (newDirection === 'down' && this.direction !== 'up') ||
            (newDirection === 'left' && this.direction !== 'right') ||
            (newDirection === 'right' && this.direction !== 'left')) {
            this.nextDirection = newDirection;
        }
    }

    gameOver() {
        this.gameState = 'gameOver';
        clearInterval(this.gameLoop);
        console.log('游戏结束，得分:', this.score);
    }

    async getRandomQuestions(count = 1, difficulty = null) {
        try {
            return await this.api.getRandomQuestions(difficulty, null, count);
        } catch (error) {
            console.error('获取题目失败:', error);
            throw error;
        }
    }

    async submitAnswer(questionId, answer) {
        if (!this.playerId) throw new Error('没有玩家ID');

        try {
            const result = await this.api.submitAnswer(this.playerId, questionId, answer);
            this.player = result.player;
            return result;
        } catch (error) {
            console.error('提交答案失败:', error);
            throw error;
        }
    }

    async getEvent(eventId) {
        try {
            return await this.api.getEvent(eventId, this.playerId);
        } catch (error) {
            console.error('获取事件失败:', error);
            throw error;
        }
    }

    async makeChoice(eventId, choiceIndex) {
        if (!this.playerId) throw new Error('没有玩家ID');

        try {
            const result = await this.api.makeChoice(this.playerId, eventId, choiceIndex);
            this.player = result.player;
            return result;
        } catch (error) {
            console.error('提交选择失败:', error);
            throw error;
        }
    }

    async getProgress() {
        if (!this.playerId) return null;

        try {
            const result = await this.api.getProgress(this.playerId);
            this.progress = result.progress;
            return result;
        } catch (error) {
            console.error('获取进度失败:', error);
            return null;
        }
    }

    async getLocations() {
        try {
            return await this.api.getLocations();
        } catch (error) {
            console.error('获取地点失败:', error);
            throw error;
        }
    }

    async getAllEvents() {
        try {
            return await this.api.getAllEvents();
        } catch (error) {
            console.error('获取事件列表失败:', error);
            throw error;
        }
    }

    async resetGame(resetAll = false) {
        if (!this.playerId) throw new Error('没有玩家ID');

        try {
            const result = await this.api.resetGame(this.playerId, resetAll);
            this.player = result.player;
            return result;
        } catch (error) {
            console.error('重置游戏失败:', error);
            throw error;
        }
    }

    savePlayerId() {
        if (this.playerId) {
            localStorage.setItem('yongzhou_player_id', this.playerId.toString());
        }
    }

    loadPlayerId() {
        const savedId = localStorage.getItem('yongzhou_player_id');
        return savedId ? parseInt(savedId) : null;
    }

    clearPlayerId() {
        localStorage.removeItem('yongzhou_player_id');
    }

    getPlayerData() {
        return {
            id: this.player?.id,
            name: this.player?.name,
            gold: this.player?.gold,
            experience: this.player?.experience,
            energy: this.player?.energy,
            reputation: this.player?.reputation,
            score: this.score,
            level: this.progress?.current_level || 1,
        };
    }
}

window.Game = Game;
