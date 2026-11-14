-- Run once as root, from backend/:  mysql -u root -p -e "source sql/01_create_db_and_user.sql"
-- Change the password below before running, and put the same one in backend/.env

CREATE DATABASE IF NOT EXISTS taskvault
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'taskvault'@'localhost' IDENTIFIED BY 'change_me_please';

-- Least privilege: this user can touch the taskvault schema and nothing else.
GRANT ALL PRIVILEGES ON taskvault.* TO 'taskvault'@'localhost';
