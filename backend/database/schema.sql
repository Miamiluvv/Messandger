-- =============================================================================
-- КОРПОРАТИВНЫЙ МЕССЕНДЖЕР ДГИ — ПОЛНАЯ СХЕМА БД
-- =============================================================================

DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ОРГАНИЗАЦИОННАЯ СТРУКТУРА
-- =============================================================================

-- Управления (Департаменты верхнего уровня)
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    short_name VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Отделы (подразделения внутри управлений)
CREATE TABLE divisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    name VARCHAR(300) NOT NULL,
    short_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ПОЛЬЗОВАТЕЛИ
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,               -- логин (i.ivanov@dgi.gov), нельзя менять
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,                 -- нельзя менять самостоятельно
    last_name VARCHAR(100) NOT NULL,                  -- нельзя менять самостоятельно
    patronymic VARCHAR(100),                          -- отчество
    avatar_url VARCHAR(500),
    phone VARCHAR(20),
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    division_id UUID REFERENCES divisions(id) ON DELETE SET NULL,
    position VARCHAR(200),                            -- должность
    role VARCHAR(30) DEFAULT 'user' CHECK (role IN (
        'super_admin',   -- Управление информатизации (полный доступ)
        'admin',         -- Администраторы
        'head',          -- Начальник управления/отдела
        'deputy_head',   -- Заместитель начальника
        'user'           -- Обычный сотрудник
    )),
    status VARCHAR(20) DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'away', 'busy')),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,                   -- активна ли учетка
    is_frozen BOOLEAN DEFAULT FALSE,                  -- заморожена упр. инф-ции
    is_blocked BOOLEAN DEFAULT FALSE,                 -- заблокирована
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),  -- дата последней смены пароля
    password_expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days'), -- 3 месяца
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ЗАПРОСЫ НА ДОСТУП (вместо самостоятельной регистрации)
-- =============================================================================

CREATE TABLE access_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    patronymic VARCHAR(100),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    department_id UUID REFERENCES departments(id),
    division_id UUID REFERENCES divisions(id),
    position VARCHAR(200),
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES users(id),
    review_comment TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ЗАПРОСЫ НА ИЗМЕНЕНИЕ ПРОФИЛЯ (смена имени/фамилии)
-- =============================================================================

CREATE TABLE profile_change_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    field_name VARCHAR(50) NOT NULL,     -- 'first_name', 'last_name', 'patronymic'
    old_value VARCHAR(200),
    new_value VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ЧАТЫ
-- =============================================================================

CREATE TABLE chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_type VARCHAR(20) NOT NULL CHECK (chat_type IN ('private', 'group', 'channel', 'saved')),
    name VARCHAR(200),
    description TEXT,
    avatar_url VARCHAR(500),
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_news_channel BOOLEAN DEFAULT FALSE,      -- новостной канал ДГИ
    is_archived BOOLEAN DEFAULT FALSE,
    max_members INTEGER DEFAULT 1000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- УЧАСТНИКИ ЧАТОВ
-- =============================================================================

CREATE TABLE chat_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'readonly')),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_read_message_id UUID,
    notifications_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,
    UNIQUE(chat_id, user_id)
);

-- =============================================================================
-- СООБЩЕНИЯ
-- =============================================================================

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT,
    message_type VARCHAR(20) DEFAULT 'text' CHECK (message_type IN (
        'text', 'file', 'image', 'video', 'audio', 'voice', 'system', 'poll'
    )),
    reply_to_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    forwarded_from_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    scheduled_at TIMESTAMP WITH TIME ZONE,          -- запланированная отправка
    is_scheduled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ВЛОЖЕНИЯ К СООБЩЕНИЯМ
-- =============================================================================

CREATE TABLE message_attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    thumbnail_url VARCHAR(500),
    width INTEGER,                                   -- для фото/видео
    height INTEGER,
    duration INTEGER,                                -- для аудио/видео (секунды)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- СТАТУСЫ ПРОЧТЕНИЯ
-- =============================================================================

CREATE TABLE message_read_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(message_id, user_id)
);

-- =============================================================================
-- РЕАКЦИИ НА СООБЩЕНИЯ
-- =============================================================================

CREATE TABLE reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(message_id, user_id, emoji)
);

-- =============================================================================
-- ОПРОСЫ
-- =============================================================================

CREATE TABLE polls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT FALSE,
    is_multiple_choice BOOLEAN DEFAULT FALSE,
    closes_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE poll_options (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    poll_id UUID NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    option_text VARCHAR(500) NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE poll_votes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    poll_id UUID NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    option_id UUID NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(poll_id, option_id, user_id)
);

-- =============================================================================
-- ЗВОНКИ
-- =============================================================================

CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID REFERENCES chats(id) ON DELETE SET NULL,
    initiator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    call_type VARCHAR(10) NOT NULL CHECK (call_type IN ('audio', 'video')),
    status VARCHAR(20) DEFAULT 'ringing' CHECK (status IN (
        'ringing', 'active', 'ended', 'missed', 'declined', 'scheduled'
    )),
    scheduled_at TIMESTAMP WITH TIME ZONE,           -- запланированный звонок
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration INTEGER,                                 -- длительность в секундах
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE call_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE,
    is_muted BOOLEAN DEFAULT FALSE,
    is_camera_off BOOLEAN DEFAULT FALSE,
    is_screen_sharing BOOLEAN DEFAULT FALSE,
    UNIQUE(call_id, user_id)
);

-- =============================================================================
-- КОНТАКТЫ
-- =============================================================================

CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_blocked BOOLEAN DEFAULT FALSE,
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, contact_id)
);

-- =============================================================================
-- СЕССИИ
-- =============================================================================

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    device_info VARCHAR(500),
    ip_address VARCHAR(45),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- =============================================================================
-- УВЕДОМЛЕНИЯ
-- =============================================================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- ПРЕДУПРЕЖДЕНИЯ ОТ АДМИНИСТРАЦИИ
-- =============================================================================

CREATE TABLE admin_announcements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    content TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    target_all BOOLEAN DEFAULT FALSE,
    target_department_id UUID REFERENCES departments(id),
    target_division_id UUID REFERENCES divisions(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- =============================================================================
-- ИНДЕКСЫ
-- =============================================================================

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_department ON users(department_id);
CREATE INDEX idx_users_division ON users(division_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_password_expires ON users(password_expires_at);

CREATE INDEX idx_divisions_department ON divisions(department_id);

CREATE INDEX idx_access_requests_status ON access_requests(status);

CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_chat_created ON messages(chat_id, created_at DESC);
CREATE INDEX idx_messages_scheduled ON messages(is_scheduled, scheduled_at) WHERE is_scheduled = TRUE;

CREATE INDEX idx_chat_members_user_id ON chat_members(user_id);
CREATE INDEX idx_chat_members_chat_id ON chat_members(chat_id);

CREATE INDEX idx_message_read_status_message ON message_read_status(message_id);
CREATE INDEX idx_message_read_status_user ON message_read_status(user_id);

CREATE INDEX idx_contacts_user_id ON contacts(user_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, is_read);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_reactions_message_id ON reactions(message_id);
CREATE INDEX idx_message_attachments_message ON message_attachments(message_id);

CREATE INDEX idx_calls_chat ON calls(chat_id);
CREATE INDEX idx_calls_initiator ON calls(initiator_id);
CREATE INDEX idx_calls_scheduled ON calls(status, scheduled_at) WHERE status = 'scheduled';
CREATE INDEX idx_call_participants_call ON call_participants(call_id);
CREATE INDEX idx_call_participants_user ON call_participants(user_id);

CREATE INDEX idx_polls_message ON polls(message_id);
CREATE INDEX idx_poll_votes_poll ON poll_votes(poll_id);

CREATE INDEX idx_admin_announcements_active ON admin_announcements(is_active, created_at DESC);

-- =============================================================================
-- ТРИГГЕРЫ
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ
-- =============================================================================

-- Управления ДГИ
INSERT INTO departments (id, name, short_name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Управление информатизации', 'УИ'),
    ('00000000-0000-0000-0000-000000000002', 'Управление государственной службы и кадров', 'УГСК'),
    ('00000000-0000-0000-0000-000000000003', 'Управление имущества', 'УИм'),
    ('00000000-0000-0000-0000-000000000004', 'Управление земельных ресурсов', 'УЗР'),
    ('00000000-0000-0000-0000-000000000005', 'Правовое управление', 'ПУ'),
    ('00000000-0000-0000-0000-000000000006', 'Управление бухгалтерского учета и отчетности', 'УБУО');

-- Администратор по умолчанию (Управление информатизации)
INSERT INTO users (id, email, password_hash, first_name, last_name, patronymic, department_id, position, role) VALUES
    ('00000000-0000-0000-0000-000000000099',
     'admin@dgi.gov',
     '$2b$12$LQv3c1yqBo9SkvXS7QTJPOuHXB.t5v8PY1i0S3k5q2e5n3X1x.qWK',  -- пароль: Admin123!
     'Администратор', 'Системный', 'Системович',
     '00000000-0000-0000-0000-000000000001',
     'Системный администратор',
     'super_admin');

-- Новостной канал ДГИ (создается автоматически)
INSERT INTO chats (id, chat_type, name, description, owner_id, is_news_channel) VALUES
    ('00000000-0000-0000-0000-000000000100',
     'channel',
     'Новости ДГИ',
     'Официальный новостной канал Департамента городского имущества',
     '00000000-0000-0000-0000-000000000099',
     TRUE);

-- Админ подписан на новостной канал
INSERT INTO chat_members (chat_id, user_id, role) VALUES
    ('00000000-0000-0000-0000-000000000100', '00000000-0000-0000-0000-000000000099', 'owner');
