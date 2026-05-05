from sqlalchemy import Column, Integer, String, Text, ForeignKey
from . import Base

class GameProgress(Base):
    __tablename__ = 'game_progress'

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, unique=True)
    current_level = Column(Integer, default=1)
    completed_events = Column(Text, default='[]')
    unlocked_branches = Column(Text, default='[]')
    achievements = Column(Text, default='[]')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'player_id': self.player_id,
            'current_level': self.current_level,
            'completed_events': json.loads(self.completed_events or '[]'),
            'unlocked_branches': json.loads(self.unlocked_branches or '[]'),
            'achievements': json.loads(self.achievements or '[]')
        }

    def add_completed_event(self, event_id):
        import json
        events = json.loads(self.completed_events or '[]')
        if event_id not in events:
            events.append(event_id)
            self.completed_events = json.dumps(events)

    def add_achievement(self, achievement):
        import json
        achievements = json.loads(self.achievements or '[]')
        if achievement not in achievements:
            achievements.append(achievement)
            self.achievements = json.dumps(achievements)
