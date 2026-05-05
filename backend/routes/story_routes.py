from flask import request, jsonify
from . import api_bp
from models import db_session, Player, StoryEvent, GameProgress
from config import Config
import json

@api_bp.route('/story/event/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = db_session.query(StoryEvent).get(event_id)

    if not event:
        return jsonify({'error': '事件不存在'}), 404

    player_id = request.args.get('player_id', type=int)

    if player_id:
        player = db_session.query(Player).get(player_id)
        if player and player.experience < event.required_experience:
            return jsonify({
                'error': f'需要{event.required_experience}经验才能解锁此事件',
                'required_experience': event.required_experience,
                'current_experience': player.experience
            }), 403

    return jsonify({
        'event': event.to_dict(include_choices=True)
    }), 200

@api_bp.route('/story/choice', methods=['POST'])
def make_choice():
    data = request.get_json()

    if not data:
        return jsonify({'error': '没有提供选择数据'}), 400

    player_id = data.get('player_id')
    event_id = data.get('event_id')
    choice_index = data.get('choice_index')

    if not all([player_id, event_id, choice_index is not None]):
        return jsonify({'error': '缺少必要参数'}), 400

    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    event = db_session.query(StoryEvent).get(event_id)
    if not event:
        return jsonify({'error': '事件不存在'}), 404

    choices = json.loads(event.choices)

    if choice_index < 0 or choice_index >= len(choices):
        return jsonify({'error': '选择索引无效'}), 400

    choice = choices[choice_index]

    rewards = choice.get('rewards', {})

    gold = rewards.get('gold', 0)
    experience = rewards.get('experience', 0)
    energy = rewards.get('energy', 0)
    reputation = rewards.get('reputation', 0)

    player.update_attributes(gold=gold, experience=experience, energy=energy, reputation=reputation)

    progress = db_session.query(GameProgress).filter_by(player_id=player_id).first()
    if progress:
        progress.add_completed_event(event_id)

        if choice.get('achievement'):
            progress.add_achievement(choice['achievement'])

        level_threshold = progress.current_level * 100
        if player.experience >= level_threshold:
            progress.current_level += 1

    db_session.commit()

    return jsonify({
        'message': '选择已提交',
        'choice_result': choice.get('result'),
        'knowledge': choice.get('knowledge'),
        'rewards': rewards,
        'player': player.to_dict(),
        'new_level': progress.current_level if progress else 1
    }), 200

@api_bp.route('/story/progress/<int:player_id>', methods=['GET'])
def get_progress(player_id):
    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    progress = db_session.query(GameProgress).filter_by(player_id=player_id).first()
    if not progress:
        return jsonify({'error': '玩家进度不存在'}), 404

    return jsonify({
        'progress': progress.to_dict()
    }), 200

@api_bp.route('/story/events', methods=['GET'])
def get_all_events():
    events = db_session.query(StoryEvent).all()
    return jsonify({
        'total': len(events),
        'events': [e.to_dict(include_choices=False) for e in events]
    }), 200

@api_bp.route('/story/events/location/<int:location_id>', methods=['GET'])
def get_events_by_location(location_id):
    events = db_session.query(StoryEvent).filter_by(location_id=location_id).all()
    return jsonify({
        'location_id': location_id,
        'events': [e.to_dict(include_choices=True) for e in events]
    }), 200
