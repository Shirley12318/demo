from flask import request, jsonify
from . import api_bp
from models import db_session, Player, GameProgress

@api_bp.route('/player/create', methods=['POST'])
def create_player():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '玩家名称不能为空'}), 400

    player = Player(
        name=data['name'],
        gold=100,
        experience=0,
        energy=100,
        reputation=0,
        position=0
    )
    db_session.add(player)
    db_session.flush()

    progress = GameProgress(player_id=player.id)
    db_session.add(progress)
    db_session.commit()

    return jsonify({
        'message': '玩家创建成功',
        'player': player.to_dict(),
        'progress': progress.to_dict()
    }), 201

@api_bp.route('/player/<int:player_id>', methods=['GET'])
def get_player(player_id):
    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    response = {'player': player.to_dict()}
    progress = db_session.query(GameProgress).filter_by(player_id=player_id).first()
    if progress:
        response['progress'] = progress.to_dict()

    return jsonify(response), 200

@api_bp.route('/player/<int:player_id>', methods=['PUT'])
def update_player(player_id):
    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': '没有提供更新数据'}), 400

    if 'name' in data:
        player.name = data['name']
    if 'gold' in data:
        player.gold = max(0, data['gold'])
    if 'experience' in data:
        player.experience = max(0, data['experience'])
    if 'energy' in data:
        player.energy = max(0, min(100, data['energy']))
    if 'reputation' in data:
        player.reputation = max(0, data['reputation'])
    if 'position' in data:
        player.position = max(0, min(99, data['position']))

    db_session.commit()
    return jsonify({
        'message': '玩家更新成功',
        'player': player.to_dict()
    }), 200

@api_bp.route('/player/<int:player_id>', methods=['DELETE'])
def delete_player(player_id):
    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    db_session.delete(player)
    db_session.commit()

    return jsonify({'message': '玩家删除成功'}), 200

@api_bp.route('/players', methods=['GET'])
def get_players():
    players = db_session.query(Player).all()
    return jsonify({
        'players': [p.to_dict() for p in players]
    }), 200


@api_bp.route('/login', methods=['POST'])
def login():
    """用户登录 - 如果用户不存在则创建新用户"""
    data = request.get_json()
    if not data or not data.get('username'):
        return jsonify({'error': '用户名不能为空'}), 400
    
    username = data.get('username')
    
    # 查找或创建玩家
    player = db_session.query(Player).filter_by(name=username).first()
    
    if not player:
        # 创建新玩家
        player = Player(
            name=username,
            gold=100,
            experience=0,
            energy=100,
            reputation=0,
            position=0
        )
        db_session.add(player)
        db_session.flush()
        
        # 创建游戏进度
        progress = GameProgress(player_id=player.id)
        db_session.add(progress)
        db_session.commit()
    else:
        # 获取现有的游戏进度
        progress = db_session.query(GameProgress).filter_by(player_id=player.id).first()
        if not progress:
            progress = GameProgress(player_id=player.id)
            db_session.add(progress)
            db_session.commit()
    
    return jsonify({
        'status': 'success',
        'message': '登录成功',
        'player': player.to_dict(),
        'progress': progress.to_dict() if progress else {}
    }), 200


@api_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    if not data or not data.get('username'):
        return jsonify({'error': '用户名不能为空'}), 400
    
    username = data.get('username')
    
    # 检查用户是否已存在
    existing_player = db_session.query(Player).filter_by(name=username).first()
    if existing_player:
        return jsonify({'error': '用户名已存在'}), 409
    
    # 创建新玩家
    player = Player(
        name=username,
        gold=100,
        experience=0,
        energy=100,
        reputation=0,
        position=0
    )
    db_session.add(player)
    db_session.flush()
    
    # 创建游戏进度
    progress = GameProgress(player_id=player.id)
    db_session.add(progress)
    db_session.commit()
    
    return jsonify({
        'status': 'success',
        'message': '注册成功',
        'player': player.to_dict(),
        'progress': progress.to_dict()
    }), 201
