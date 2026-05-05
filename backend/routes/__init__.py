from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from .player_routes import *
from .game_routes import *
from .question_routes import *
from .story_routes import *
from .location_routes import *
from .discussion_routes import *
