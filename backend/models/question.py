from sqlalchemy import Column, Integer, String, Text
from . import Base

class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    options = Column(Text, nullable=False)
    correct_answer = Column(Integer, nullable=False)
    difficulty = Column(Integer, default=1)
    category = Column(String(50), default='history')
    explanation = Column(Text)

    def to_dict(self, include_answer=False):
        import json
        data = {
            'id': self.id,
            'question': self.question,
            'options': json.loads(self.options),
            'difficulty': self.difficulty,
            'category': self.category
        }
        if include_answer:
            data['correct_answer'] = self.correct_answer
            data['explanation'] = self.explanation
        return data
