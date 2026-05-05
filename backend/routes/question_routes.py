from flask import request, jsonify
from . import api_bp
from models import db_session, Player, Question
from config import Config
import random
import json

@api_bp.route('/question/random', methods=['GET'])
def get_random_question():
    difficulty = request.args.get('difficulty', type=int)
    category = request.args.get('category')
    count = request.args.get('count', 1, type=int)

    query = db_session.query(Question)

    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if category:
        query = query.filter_by(category=category)

    questions = query.all()

    if not questions:
        return jsonify({'error': '没有找到符合条件的题目'}), 404

    selected = random.sample(questions, min(count, len(questions)))

    return jsonify({
        'questions': [q.to_dict(include_answer=False) for q in selected]
    }), 200

@api_bp.route('/question/category/<string:category>', methods=['GET'])
def get_questions_by_category(category):
    questions = db_session.query(Question).filter_by(category=category).all()

    if not questions:
        return jsonify({'error': f'没有找到分类为"{category}"的题目'}), 404

    return jsonify({
        'category': category,
        'questions': [q.to_dict(include_answer=False) for q in questions]
    }), 200

@api_bp.route('/question/answer', methods=['POST'])
def submit_answer():
    data = request.get_json()

    if not data:
        return jsonify({'error': '没有提供答案数据'}), 400

    player_id = data.get('player_id')
    question_id = data.get('question_id')
    answer = data.get('answer')

    if not all([player_id, question_id, answer is not None]):
        return jsonify({'error': '缺少必要参数'}), 400

    player = db_session.query(Player).get(player_id)
    if not player:
        return jsonify({'error': '玩家不存在'}), 404

    question = db_session.query(Question).get(question_id)
    if not question:
        return jsonify({'error': '题目不存在'}), 404

    is_correct = (answer == question.correct_answer)

    result = {
        'is_correct': is_correct,
        'correct_answer': question.correct_answer if not is_correct else None,
        'explanation': question.explanation
    }

    if is_correct:
        difficulty_bonus = Config.DIFFICULTIES[question.difficulty]['reward_bonus']
        rewards = {
            'gold': int(Config.REWARDS['correct_answer']['gold'] * difficulty_bonus),
            'experience': int(Config.REWARDS['correct_answer']['experience'] * difficulty_bonus),
            'energy': Config.REWARDS['correct_answer']['energy']
        }
        player.update_attributes(**rewards)
        db_session.commit()

        result['rewards'] = rewards
        result['player'] = player.to_dict()
    else:
        player.update_attributes(**Config.REWARDS['wrong_answer'])
        db_session.commit()

        result['rewards'] = Config.REWARDS['wrong_answer']
        result['player'] = player.to_dict()

    return jsonify(result), 200

@api_bp.route('/questions', methods=['GET'])
def get_all_questions():
    questions = db_session.query(Question).all()
    return jsonify({
        'total': len(questions),
        'questions': [q.to_dict(include_answer=False) for q in questions]
    }), 200
