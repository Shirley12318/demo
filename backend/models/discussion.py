from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from . import Base

class DiscussionTopic(Base):
    __tablename__ = 'discussion_topics'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DiscussionPost(Base):
    __tablename__ = 'discussion_posts'
    
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer)  # 对应讨论主题
    author_name = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    liked_by = Column(String(1000), default='')  # JSON字符串，存储点赞用户
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self, current_user=None):
        liked_users = self.liked_by.split(',') if self.liked_by else []
        is_liked = current_user in liked_users if current_user else False
        
        return {
            'id': self.id,
            'topic_id': self.topic_id,
            'author_name': self.author_name,
            'title': self.title,
            'content': self.content,
            'likes': self.likes,
            'comments': self.comments,
            'favorites': self.favorites,
            'is_liked': is_liked,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
