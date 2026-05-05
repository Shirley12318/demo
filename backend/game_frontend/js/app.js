(function() {
    const game = new Game();
    let gameUI = null;

    async function init() {
        gameUI = new GameUI(game);
        gameUI.init();

        const canvas = document.getElementById('game-board');
        await game.init(canvas);

        checkSavedPlayer();

        bindEventListeners();
        bindKeyboardControls();
    }

    function checkSavedPlayer() {
        const savedPlayerId = game.loadPlayerId();
        if (savedPlayerId) {
            document.getElementById('btn-continue').style.display = 'inline-block';
        }
    }

    function bindEventListeners() {
        document.getElementById('btn-new-game').addEventListener('click', showCreatePlayerScreen);
        document.getElementById('btn-continue').addEventListener('click', continueGame);
        document.getElementById('btn-confirm-create').addEventListener('click', createNewPlayer);
        document.getElementById('btn-back-to-start').addEventListener('click', () => gameUI.showScreen('start-screen'));

        document.getElementById('btn-show-map').addEventListener('click', () => gameUI.showLocations());
        document.getElementById('btn-show-questions').addEventListener('click', () => gameUI.showQuestion());
        document.getElementById('btn-show-story').addEventListener('click', () => gameUI.showStoryProgress());
        document.getElementById('btn-pause').addEventListener('click', () => openModal('pause-modal'));

        document.getElementById('btn-resume').addEventListener('click', () => closeModal('pause-modal'));
        document.getElementById('btn-save-quit').addEventListener('click', saveAndQuit);

        document.getElementById('btn-submit-answer').addEventListener('click', () => gameUI.submitAnswer());
        document.getElementById('btn-next-question').addEventListener('click', () => {
            closeModal('question-modal');
            gameUI.showQuestion();
        });
    }

    function bindKeyboardControls() {
        document.addEventListener('keydown', (e) => {
            switch (e.key) {
                case 'ArrowUp':
                    game.setDirection('up');
                    break;
                case 'ArrowDown':
                    game.setDirection('down');
                    break;
                case 'ArrowLeft':
                    game.setDirection('left');
                    break;
                case 'ArrowRight':
                    game.setDirection('right');
                    break;
            }
        });
    }

    async function showCreatePlayerScreen() {
        document.getElementById('player-name-input').value = '';
        gameUI.showScreen('create-player-screen');
    }

    async function createNewPlayer() {
        const nameInput = document.getElementById('player-name-input');
        const name = nameInput.value.trim();

        if (!name) {
            alert('请输入玩家名称');
            return;
        }

        try {
            await game.createPlayer(name);
            startGame();
        } catch (error) {
            alert('创建玩家失败: ' + error.message);
        }
    }

    async function continueGame() {
        const savedPlayerId = game.loadPlayerId();
        if (!savedPlayerId) {
            showCreatePlayerScreen();
            return;
        }

        try {
            await game.loadPlayer(savedPlayerId);
            startGame();
        } catch (error) {
            game.clearPlayerId();
            showCreatePlayerScreen();
        }
    }

    async function startGame() {
        gameUI.showScreen('game-screen');
        gameUI.updatePlayerDisplay();
        game.startGame();
        gameUI.showMessage('欢迎来到永州！使用方向键控制贪吃蛇，吃到苹果触发红色文化事件！', 'success');
    }



    async function saveAndQuit() {
        closeModal('pause-modal');
        gameUI.showScreen('start-screen');
        gameUI.showMessage('游戏已保存！');
    }

    document.addEventListener('DOMContentLoaded', init);
})();
