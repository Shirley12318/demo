from flask import request, jsonify
from . import api_bp
from models import db_session, Player
from config import Config
import random

last_roll_value = None
consecutive_rolls = 0

def calculate_position(current_pos, dice_value):
    new_pos = (current_pos + dice_value) % Config.TOTAL_POSITIONS
    return new_pos

def get_cell_type(position):
    mod = position % 5
    types = ['history', 'question', 'opportunity', 'safe', 'special']
    return types[mod]

@api_bp.route('/game/roll', methods=['POST'])
def roll_dice():
    global last_roll_value, consecutive_rolls

    data = request.get_json() or {}
    use_special = data.get('special', False)

    if use_special:
        dice_value = random.randint(1, 9)
    else:
        dice_value = random.randint(Config.DICE_MIN, Config.DICE_MAX)

    if dice_value == last_roll_value:
        consecutive_rolls += 1
        is_combo = True
    else:
        consecutive_rolls = 1
        is_combo = False

    last_roll_value = dice_value

    return jsonify({
        'dice_value': dice_value,
        'is_combo': is_combo,
        'combo_count': consecutive_rolls,
        'special_roll': use_special
    }), 200

@api_bp.route('/game/board', methods=['GET'])
def get_board():
    board = []
    for i in range(Config.TOTAL_POSITIONS):
        cell_type = get_cell_type(i)
        color = Config.CELL_TYPES[cell_type]['color']
        name = Config.CELL_TYPES[cell_type]['name']
        board.append({
            'position': i,
            'type': cell_type,
            'color': color,
            'name': name
        })

    players = db_session.query(Player).all()
    player_positions = [{'id': p.id, 'name': p.name, 'position': p.position} for p in players]

    return jsonify({
        'board': board,
        'players': player_positions,
        'board_size': Config.BOARD_SIZE
    }), 200

@api_bp.route('/game/move/<int:player_id>', methods=['POST'])
def move_player(player_id):
    global last_roll_value

    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    data = request.get_json() or {}
    dice_value = data.get('dice_value')

    if dice_value is None:
        return jsonify({'error': '没有提供骰子值'}), 400

    if not isinstance(dice_value, int) or dice_value < 1 or dice_value > 9:
        return jsonify({'error': '骰子值无效'}), 400

    if player.energy < 10:
        return jsonify({'error': '体力不足，无法移动'}), 400

    old_position = player.position
    new_position = calculate_position(old_position, dice_value)

    player.position = new_position
    player.energy = max(0, player.energy - 5)

    db_session.commit()

    cell_type = get_cell_type(new_position)
    cell_info = {
        'type': cell_type,
        'color': Config.CELL_TYPES[cell_type]['color'],
        'name': Config.CELL_TYPES[cell_type]['name']
    }

    return jsonify({
        'message': '移动成功',
        'player': player.to_dict(),
        'old_position': old_position,
        'new_position': new_position,
        'dice_value': dice_value,
        'cell': cell_info
    }), 200

@api_bp.route('/game/reset/<int:player_id>', methods=['POST'])
def reset_game(player_id):
    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    data = request.get_json() or {}
    reset_all = data.get('reset_all', False)

    player.position = 0
    player.energy = 100

    if reset_all:
        player.gold = Config.INITIAL_GOLD
        player.experience = Config.INITIAL_EXPERIENCE
        player.reputation = Config.INITIAL_REPUTATION

    db_session.commit()

    return jsonify({
        'message': '游戏重置成功',
        'player': player.to_dict()
    }), 200

@api_bp.route('/game/cell/<int:position>', methods=['GET'])
def get_cell_info(position):
    if position < 0 or position >= Config.TOTAL_POSITIONS:
        return jsonify({'error': '位置无效'}), 400

    cell_type = get_cell_type(position)
    return jsonify({
        'position': position,
        'type': cell_type,
        'color': Config.CELL_TYPES[cell_type]['color'],
        'name': Config.CELL_TYPES[cell_type]['name']
    }), 200
