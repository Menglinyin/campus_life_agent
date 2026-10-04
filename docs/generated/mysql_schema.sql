-- GENERATED FROM SQLALCHEMY ORM. Reference only; not a migration.

-- Python defaults are not SERVER DEFAULT clauses.

-- No database was connected to generate this file.

CREATE TABLE classrooms (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE courses (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE dishes (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE feedback (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE knowledge_chunks (
	id VARCHAR(64) NOT NULL, 
	source VARCHAR(255) NOT NULL, 
	owner VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_knowledge_chunks_owner ON knowledge_chunks (owner);

CREATE TABLE projection_jobs (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE secondhand (
	id VARCHAR(64) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE chat_sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	slots JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_chat_sessions_user_id ON chat_sessions (user_id);

CREATE TABLE user_preferences (
	user_id VARCHAR(64) NOT NULL, 
	`values` JSON NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE chat_messages (
	id VARCHAR(36) NOT NULL, 
	session_id VARCHAR(36) NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	content TEXT NOT NULL, 
	payload JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES chat_sessions (id)
);

CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);
