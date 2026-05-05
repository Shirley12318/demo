from sqlalchemy import Column, Integer, String, Text, ForeignKey
from . import Base

class StoryEvent(Base):
    __tablename__ = 'story_events'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'))
    choices = Column(Text, nullable=False)
    required_experience = Column(Integer, default=0)

    def to_dict(self, include_choices=False):
        import json
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'location_id': self.location_id,
            'required_experience': self.required_experience
        }
        if include_choices:
            data['choices'] = json.loads(self.choices)
        return data
