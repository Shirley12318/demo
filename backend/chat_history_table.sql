-- 创建聊天会话表
CREATE TABLE IF NOT EXISTS chat_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '会话ID',
    user_id INT NOT NULL COMMENT '用户ID，关联users表',
    title VARCHAR(255) NOT NULL DEFAULT '新对话' COMMENT '会话标题',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_chat_conversations_user_id (user_id),
    INDEX idx_chat_conversations_updated_at (updated_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户聊天会话表';

-- 创建聊天历史记录表
CREATE TABLE IF NOT EXISTS chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    user_id INT NOT NULL COMMENT '用户ID，关联users表',
    conversation_id INT DEFAULT NULL COMMENT '所属会话ID，关联chat_conversations表',
    
    -- 用户消息相关
    user_message TEXT NOT NULL COMMENT '用户发送的消息内容',
    user_emotion_score DECIMAL(5,2) DEFAULT NULL COMMENT '用户情感评分(0-100)',
    user_ideal_belief DECIMAL(5,2) DEFAULT NULL COMMENT '理想信念强度(0-100)',
    user_logic_thinking DECIMAL(5,2) DEFAULT NULL COMMENT '逻辑思维能力(0-100)',
    user_practice_ability DECIMAL(5,2) DEFAULT NULL COMMENT '实践能力(0-100)',
    user_psychological_quality DECIMAL(5,2) DEFAULT NULL COMMENT '心理素质(0-100)',
    user_hidden_needs TEXT DEFAULT NULL COMMENT '隐性需求，逗号分隔',
    user_interest_themes TEXT DEFAULT NULL COMMENT '兴趣主题，逗号分隔',
    
    -- AI回复相关
    ai_reply TEXT NOT NULL COMMENT 'AI回复内容',
    ai_reply_score INT DEFAULT NULL COMMENT 'AI回复评分(0-100)',
    ai_reply_feedback TEXT DEFAULT NULL COMMENT 'AI回复改进意见',
    selected_model VARCHAR(50) DEFAULT NULL COMMENT '选择的模型(Qwen/DeepSeek/Kimi)',
    
    -- 模型对比信息
    qwen_score INT DEFAULT NULL COMMENT 'Qwen模型评分',
    deepseek_score INT DEFAULT NULL COMMENT 'DeepSeek模型评分',
    kimi_score INT DEFAULT NULL COMMENT 'Kimi模型评分',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    -- 索引
    INDEX idx_user_id (user_id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与AI聊天历史记录表';

-- 已有 chat_history 表的增量修改示例
-- ALTER TABLE chat_history ADD COLUMN conversation_id INT DEFAULT NULL COMMENT '所属会话ID' AFTER user_id;
-- CREATE INDEX idx_conversation_id ON chat_history (conversation_id);
