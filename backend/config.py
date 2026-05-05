import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'shaoshan-red-culture-game-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///data/shaoshan.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ['http://localhost:5000', 'http://127.0.0.1:5000', 'http://localhost:3000', 'http://127.0.0.1:3000', 'file://']

    BOARD_SIZE = 10
    TOTAL_POSITIONS = 100

    INITIAL_GOLD = 100
    INITIAL_EXPERIENCE = 0
    INITIAL_ENERGY = 100
    INITIAL_REPUTATION = 0

    DICE_MIN = 1
    DICE_MAX = 6

    CELL_TYPES = {
        'history': {'color': '#FF6B6B', 'name': '历史事件', 'reward_multiplier': 1.5},
        'question': {'color': '#FFA07A', 'name': '知识问答', 'reward_multiplier': 1.2},
        'opportunity': {'color': '#FFD700', 'name': '机遇', 'reward_multiplier': 2.0},
        'safe': {'color': '#90EE90', 'name': '安全', 'reward_multiplier': 0},
        'special': {'color': '#FF8C42', 'name': '特殊', 'reward_multiplier': 2.5}
    }

    REWARDS = {
        'correct_answer': {'gold': 20, 'experience': 15, 'energy': 5},
        'wrong_answer': {'gold': -10, 'experience': 0, 'energy': -5},
        'good_choice': {'gold': 30, 'experience': 25, 'reputation': 5},
        'bad_choice': {'gold': -15, 'experience': -10, 'reputation': -3},
        'opportunity_good': {'gold': 50, 'experience': 30, 'reputation': 10},
        'opportunity_bad': {'gold': -30, 'experience': -15, 'reputation': -5}
    }

    DIFFICULTIES = {
        1: {'name': '简单', 'time_limit': None, 'reward_bonus': 1.0},
        2: {'name': '中等', 'time_limit': 15, 'reward_bonus': 1.5},
        3: {'name': '困难', 'time_limit': 10, 'reward_bonus': 2.0}
    }
