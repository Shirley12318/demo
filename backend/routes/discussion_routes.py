from flask import request, jsonify
from . import api_bp
from models import db_session, DiscussionTopic, DiscussionPost
from datetime import datetime
import json


# 获取所有讨论主题
@api_bp.route('/discussion/topics', methods=['GET'])
def get_discussion_topics():
    try:
        topics = db_session.query(DiscussionTopic).all()
        return jsonify({
            'status': 'success',
            'topics': [t.name for t in topics]  # 只返回主题名称
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 获取讨论帖子列表
@api_bp.route('/discussion/posts', methods=['GET'])
def get_discussion_posts():
    try:
        topic = request.args.get('topic', '')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        username = request.args.get('username')
        
        query = db_session.query(DiscussionPost)
        
        # 如果指定了主题，按主题筛选
        if topic:
            topic_obj = db_session.query(DiscussionTopic).filter_by(name=topic).first()
            if topic_obj:
                query = query.filter_by(topic_id=topic_obj.id)
        
        # 按创建时间排序
        posts = query.order_by(DiscussionPost.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'status': 'success',
            'posts': [p.to_dict(username) for p in posts]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 创建讨论帖子
@api_bp.route('/discussion/posts', methods=['POST'])
def create_discussion_post():
    try:
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('title') or not data.get('content'):
            return jsonify({'error': '缺少必要字段'}), 400
        
        topic_name = data.get('topic', '讨论')
        
        # 查找或创建主题
        topic = db_session.query(DiscussionTopic).filter_by(name=topic_name).first()
        if not topic:
            topic = DiscussionTopic(name=topic_name)
            db_session.add(topic)
            db_session.flush()
        
        # 创建帖子
        post = DiscussionPost(
            topic_id=topic.id,
            author_name=data.get('username'),
            title=data.get('title'),
            content=data.get('content'),
            likes=0,
            comments=0,
            favorites=0
        )
        db_session.add(post)
        db_session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '帖子发布成功',
            'post': post.to_dict()
        }), 201
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': str(e)}), 500


# 点赞帖子
@api_bp.route('/discussion/posts/<int:post_id>/like', methods=['POST'])
def toggle_like_post(post_id):
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        
        post = db_session.query(DiscussionPost).get(post_id)
        if not post:
            return jsonify({'error': '帖子不存在'}), 404
        
        liked_users = post.liked_by.split(',') if post.liked_by else []
        liked_users = [u for u in liked_users if u]  # 清理空字符串
        
        if username in liked_users:
            # 取消点赞
            liked_users.remove(username)
            post.likes = max(0, post.likes - 1)
            action = 'unlike'
        else:
            # 点赞
            liked_users.append(username)
            post.likes += 1
            action = 'like'
        
        post.liked_by = ','.join(liked_users)
        db_session.commit()
        
        return jsonify({
            'status': 'success',
            'action': action,
            'likes': post.likes
        }), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': str(e)}), 500


# 举报帖子
@api_bp.route('/discussion/posts/<int:post_id>/report', methods=['POST'])
def report_post(post_id):
    try:
        data = request.get_json()
        username = data.get('username')
        reason = data.get('reason', '违规内容')
        
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        
        post = db_session.query(DiscussionPost).get(post_id)
        if not post:
            return jsonify({'error': '帖子不存在'}), 404
        
        # 记录举报（这里可以存储到数据库，暂时只返回成功）
        
        return jsonify({
            'status': 'success',
            'message': f'已举报帖子，原因：{reason}',
            'post_id': post_id
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 初始化讨论主题数据
def init_discussion_topics():
    """初始化默认的讨论主题"""
    default_topics = [
        '理论学习',
        '时政热点',
        '二十大精神',
        '乡村振兴',
        '社区建设',
        '家庭教育',
        '传统文化',
        '生态文明',
        '职业发展',
        '心理健康',
        '志愿服务',
        '读书分享'
    ]
    
    for topic_name in default_topics:
        existing = db_session.query(DiscussionTopic).filter_by(name=topic_name).first()
        if not existing:
            topic = DiscussionTopic(name=topic_name)
            db_session.add(topic)
    
    db_session.commit()
