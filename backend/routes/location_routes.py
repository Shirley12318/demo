from flask import jsonify
from . import api_bp
from models import db_session, Location

@api_bp.route('/locations', methods=['GET'])
def get_locations():
    locations = db_session.query(Location).all()
    return jsonify({
        'total': len(locations),
        'locations': [loc.to_dict() for loc in locations]
    }), 200

@api_bp.route('/location/<int:location_id>', methods=['GET'])
def get_location(location_id):
    location = db_session.query(Location).get(location_id)

    if not location:
        return jsonify({'error': '地点不存在'}), 404

    return jsonify({
        'location': location.to_dict()
    }), 200

@api_bp.route('/locations/landmarks', methods=['GET'])
def get_landmarks():
    locations = db_session.query(Location).filter_by(is_landmark=True).all()
    return jsonify({
        'total': len(locations),
        'locations': [loc.to_dict() for loc in locations]
    }), 200
