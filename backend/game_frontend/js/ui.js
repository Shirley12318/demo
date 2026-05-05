class GameUI {
    constructor(game) {
        this.game = game;
        this.canvas = document.getElementById('game-board');
        this.ctx = this.canvas.getContext('2d');
        this.cellSize = 50;
        this.boardSize = 10;
        this.currentQuestion = null;
        this.selectedAnswer = null;
    }

    init() {
        this.setupCanvas();
        this.bindEvents();
    }
    setupCanvas() {
        const container = document.getElementById('board-container');

        // 1. 增加安全检查：如果容器不存在，给个默认值，防止报错
        const containerWidth = container ? container.clientWidth : 600;

        // 2. 计算最大尺寸
        const maxSize = Math.min(containerWidth - 40, 550);

        // 3. 【关键修改】强制最小尺寸：
        // 防止因容器太小（或CSS未加载完）导致计算出的尺寸过小或为负数
        // 保证棋盘至少是 500px，这样 cellSize 至少是 50
        const safeMaxSize = Math.max(maxSize, 500);

        this.cellSize = Math.floor(safeMaxSize / this.boardSize);

        this.canvas.width = this.cellSize * this.boardSize;
        this.canvas.height = this.cellSize * this.boardSize;
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            this.setupCanvas();
            this.drawBoard();
        });
    }

    drawBoard() {
        if (!this.game.board) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const cellColors = {
            'history': '#FF6B6B',
            'question': '#FFA07A',
            'opportunity': '#FFD700',
            'safe': '#90EE90',
            'special': '#FF8C42'
        };

        for (let i = 0; i < 100; i++) {
            const col = i % this.boardSize;
            const row = Math.floor(i / this.boardSize);

            let x, y;
            if (row % 2 === 0) {
                x = col * this.cellSize;
            } else {
                x = (this.boardSize - 1 - col) * this.cellSize;
            }
            y = row * this.cellSize;

            const cell = this.game.board.board.find(c => c.position === i);
            const color = cell ? cellColors[cell.type] || '#FFFFFF' : '#FFFFFF';

            this.ctx.fillStyle = color;
            this.ctx.fillRect(x + 2, y + 2, this.cellSize - 4, this.cellSize - 4);

            this.ctx.fillStyle = '#4A2C2C';
            this.ctx.font = `${Math.floor(this.cellSize / 4)}px Arial`;
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText((i + 1).toString(), x + this.cellSize / 2, y + this.cellSize / 2);

            if (this.game.player && this.game.player.position === i) {
                this.drawPlayer(x + this.cellSize / 2, y + this.cellSize / 2);
            }
        }
    }

    drawPlayer(x, y) {
        this.ctx.fillStyle = '#E85A4F';
        this.ctx.beginPath();
        this.ctx.arc(x, y, this.cellSize / 4, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.font = `bold ${Math.floor(this.cellSize / 4)}px Arial`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('我', x, y);
    }

    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        const screen = document.getElementById(screenId);
        if (screen) {
            screen.classList.add('active');
        }
    }

    updatePlayerDisplay() {
        const data = this.game.getPlayerData();

        document.getElementById('display-player-name').textContent = data.name || '玩家';
        document.getElementById('display-level').textContent = data.level || 1;
        document.getElementById('display-gold').textContent = data.gold ?? 0;
        document.getElementById('display-experience').textContent = data.experience ?? 0;
        document.getElementById('display-energy').textContent = data.energy ?? 0;
        document.getElementById('display-reputation').textContent = data.reputation ?? 0;
    }

    showMessage(text, type = 'info') {
        const messageEl = document.getElementById('game-message');
        messageEl.textContent = text;
        messageEl.style.color = type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#E85A4F';
    }

    async showEvent(eventId) {
        try {
            const result = await this.game.getEvent(eventId);
            const event = result.event;

            document.getElementById('event-title').textContent = event.title;
            document.getElementById('event-location').textContent = `📍 地点 ID: ${event.location_id}`;
            document.getElementById('event-description').textContent = event.description;

            const choicesContainer = document.getElementById('event-choices');
            choicesContainer.innerHTML = '';

            const choices = event.choices;
            choices.forEach((choice, index) => {
                const btn = document.createElement('button');
                btn.className = 'choice-btn';
                btn.textContent = `${index + 1}. ${choice.text}`;
                btn.onclick = () => this.handleChoice(eventId, index);
                choicesContainer.appendChild(btn);
            });

            openModal('event-modal');
        } catch (error) {
            if (error.message.includes('经验')) {
                this.showMessage(error.message, 'error');
            } else {
                this.showMessage('获取事件失败', 'error');
            }
        }
    }

    async handleChoice(eventId, choiceIndex) {
        try {
            closeModal('event-modal');
            const result = await this.game.makeChoice(eventId, choiceIndex);

            this.updatePlayerDisplay();

            this.showMessage(`选择了: ${result.choice_result}`);

            if (result.new_level && result.new_level > (this.game.progress?.current_level || 1)) {
                document.getElementById('new-level').textContent = result.new_level;
                openModal('level-up-modal');
            }
        } catch (error) {
            this.showMessage('选择失败: ' + error.message, 'error');
        }
    }

    async showQuestion(difficulty = null) {
        try {
            const result = await this.game.getRandomQuestions(1, difficulty);
            if (!result.questions || result.questions.length === 0) {
                this.showMessage('没有可用的题目', 'error');
                return;
            }

            this.currentQuestion = result.questions[0];
            this.selectedAnswer = null;

            document.getElementById('question-title').textContent = '📚 知识问答';

            const difficultyEl = document.getElementById('question-difficulty');
            const difficultyNames = { 1: '简单', 2: '中等', 3: '困难' };
            const diff = this.currentQuestion.difficulty;
            difficultyEl.innerHTML = `<span class="difficulty-badge difficulty-${diff}">${difficultyNames[diff] || '未知'}</span>`;

            document.getElementById('question-text').textContent = this.currentQuestion.question;

            const optionsContainer = document.getElementById('question-options');
            optionsContainer.innerHTML = '';

            this.currentQuestion.options.forEach((option, index) => {
                const btn = document.createElement('button');
                btn.className = 'option-btn';
                btn.textContent = option;
                btn.onclick = () => this.selectAnswer(index, btn);
                optionsContainer.appendChild(btn);
            });

            document.getElementById('question-result').style.display = 'none';
            document.getElementById('question-explanation').style.display = 'none';
            document.getElementById('btn-submit-answer').style.display = 'inline-block';
            document.getElementById('btn-next-question').style.display = 'none';
            document.getElementById('btn-close-question').style.display = 'none';

            openModal('question-modal');
        } catch (error) {
            this.showMessage('获取题目失败', 'error');
        }
    }

    selectAnswer(index, btnElement) {
        document.querySelectorAll('.option-btn').forEach(btn => {
            btn.classList.remove('selected');
        });
        btnElement.classList.add('selected');
        this.selectedAnswer = index;
    }

    async submitAnswer() {
        if (this.selectedAnswer === null) {
            this.showMessage('请选择一个答案', 'error');
            return;
        }

        try {
            const result = await this.game.submitAnswer(this.currentQuestion.id, this.selectedAnswer);

            const optionsBtns = document.querySelectorAll('.option-btn');
            optionsBtns.forEach((btn, index) => {
                btn.style.pointerEvents = 'none';
                if (index === result.correct_answer) {
                    btn.classList.add('correct');
                } else if (index === this.selectedAnswer && !result.is_correct) {
                    btn.classList.add('wrong');
                }
            });

            const resultEl = document.getElementById('question-result');
            resultEl.style.display = 'block';
            resultEl.className = `question-result ${result.is_correct ? 'correct' : 'wrong'}`;
            resultEl.textContent = result.is_correct ? '🎉 回答正确！' : '❌ 回答错误';

            const explanationEl = document.getElementById('question-explanation');
            explanationEl.style.display = 'block';
            explanationEl.textContent = result.explanation;

            document.getElementById('btn-submit-answer').style.display = 'none';

            if (result.is_correct) {
                document.getElementById('btn-next-question').style.display = 'inline-block';
            } else {
                document.getElementById('btn-close-question').style.display = 'inline-block';
            }

            this.updatePlayerDisplay();
        } catch (error) {
            this.showMessage('提交答案失败', 'error');
        }
    }

    async showLocations() {
        try {
            const result = await this.game.getLocations();
            const container = document.getElementById('location-list');
            container.innerHTML = '';

            result.locations.forEach(loc => {
                const item = document.createElement('div');
                item.className = 'location-item';
                item.innerHTML = `
                    <h4>${loc.is_landmark ? '🏛️' : '📍'} ${loc.name}</h4>
                    <p>${loc.description || '暂无描述'}</p>
                `;
                container.appendChild(item);
            });

            openModal('location-modal');
        } catch (error) {
            this.showMessage('获取地点失败', 'error');
        }
    }

    async showStoryProgress() {
        try {
            const result = await this.game.getProgress();
            if (!result) {
                this.showMessage('获取进度失败', 'error');
                return;
            }

            const progress = result.progress;
            document.getElementById('story-level').textContent = progress.current_level || 1;
            document.getElementById('story-completed').textContent = (progress.completed_events || []).length;
            document.getElementById('story-achievements').textContent = (progress.achievements || []).length;

            const container = document.getElementById('achievement-list');
            container.innerHTML = '';

            const achievements = progress.achievements || [];
            if (achievements.length === 0) {
                container.innerHTML = '<p style="text-align:center;color:#999;">暂无成就</p>';
            } else {
                achievements.forEach(ach => {
                    const item = document.createElement('div');
                    item.className = 'achievement-item';
                    item.innerHTML = `<span class="achievement-icon">🏆</span><span>${ach}</span>`;
                    container.appendChild(item);
                });
            }

            openModal('story-modal');
        } catch (error) {
            this.showMessage('获取剧情进度失败', 'error');
        }
    }

    rollDiceAnimation(diceElement, callback) {
        diceElement.classList.add('rolling');
        let rollCount = 0;
        const maxRolls = 10;
        const rollInterval = setInterval(() => {
            const tempValue = Math.floor(Math.random() * 6) + 1;
            diceElement.textContent = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][tempValue - 1];
            rollCount++;

            if (rollCount >= maxRolls) {
                clearInterval(rollInterval);
                diceElement.classList.remove('rolling');
                callback();
            }
        }, 100);
    }
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

window.GameUI = GameUI;
window.openModal = openModal;
window.closeModal = closeModal;
