from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from . import Base

class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    gold = Column(Integer, default=100)
    experience = Column(Integer, default=0)
    energy = Column(Integer, default=100)
    reputation = Column(Integer, default=0)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gold': self.gold,
            'experience': self.experience,
            'energy': self.energy,
            'reputation': self.reputation,
            'position': self.position,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def update_attributes(self, gold=0, experience=0, energy=0, reputation=0):
        self.gold = max(0, self.gold + gold)
        self.experience = max(0, self.experience + experience)
        self.energy = max(0, min(100, self.energy + energy))
        self.reputation = max(0, self.reputation + reputation)
