from sqlalchemy import Column, Integer, String, Text, Boolean
from . import Base

class Location(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    image_url = Column(String(500))
    is_landmark = Column(Boolean, default=False)
    cultural_significance = Column(Text)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'is_landmark': self.is_landmark,
            'cultural_significance': self.cultural_significance
        }
