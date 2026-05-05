-- 创建用户讨论区帖子表
CREATE TABLE IF NOT EXISTS discussion_posts (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '讨论帖ID',
    user_id INT NOT NULL COMMENT '发帖用户ID，关联users表',
    topic VARCHAR(120) NOT NULL COMMENT '讨论主题',
    title VARCHAR(255) NOT NULL COMMENT '帖子标题',
    content TEXT NOT NULL COMMENT '帖子内容',
    like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数',
    report_count INT NOT NULL DEFAULT 0 COMMENT '举报数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_discussion_posts_topic_created_at (topic, created_at),
    INDEX idx_discussion_posts_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户讨论区帖子表';

-- 创建讨论帖点赞记录表
CREATE TABLE IF NOT EXISTS discussion_post_likes (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '点赞记录ID',
    post_id INT NOT NULL COMMENT '帖子ID，关联discussion_posts表',
    user_id INT NOT NULL COMMENT '点赞用户ID，关联users表',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',

    UNIQUE KEY uniq_discussion_like (post_id, user_id),
    INDEX idx_discussion_post_likes_user_id (user_id),
    FOREIGN KEY (post_id) REFERENCES discussion_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讨论帖点赞记录表';

-- 创建讨论帖举报记录表
CREATE TABLE IF NOT EXISTS discussion_post_reports (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '举报记录ID',
    post_id INT NOT NULL COMMENT '帖子ID，关联discussion_posts表',
    user_id INT NOT NULL COMMENT '举报用户ID，关联users表',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '举报时间',

    UNIQUE KEY uniq_discussion_report (post_id, user_id),
    INDEX idx_discussion_post_reports_user_id (user_id),
    FOREIGN KEY (post_id) REFERENCES discussion_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='讨论帖举报记录表';