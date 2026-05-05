import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
from models import Base, db_session, Player, GameProgress, Question, StoryEvent, Location
from sqlalchemy import create_engine

def create_app():
    app = Flask(__name__, static_folder='game_frontend', static_url_path='')
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    db_path = os.path.join(os.path.dirname(__file__), 'data', 'shaoshan.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db_uri = f'sqlite:///{db_path}'

    engine = create_engine(db_uri)
    db_session.registry.clear()
    db_session.configure(bind=engine)

    Base.metadata.create_all(engine)

    from routes import api_bp
    app.register_blueprint(api_bp)

    @app.route('/')
    def serve_index():
        frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'game_frontend'))
        return send_from_directory(frontend_path, 'index.html')

    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'message': '韶山红色文化游戏服务运行中'}), 200

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '资源未找到'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': '服务器内部错误'}), 500

    with app.app_context():
        from data_loader import load_initial_data
        from routes.discussion_routes import init_discussion_topics
        load_initial_data(app)
        init_discussion_topics()

    return app
