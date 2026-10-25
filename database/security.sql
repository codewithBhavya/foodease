-- Database security: separate accounts with the minimum privileges needed.
-- Run as the MySQL root user, then put the app account in your .env file.

-- The web application: can read and write data, cannot change the structure.
CREATE USER IF NOT EXISTS 'foodease_app'@'localhost' IDENTIFIED BY 'ChangeThisAppPassword!1';
GRANT SELECT, INSERT, UPDATE, DELETE ON foodease.* TO 'foodease_app'@'localhost';

-- A reporting account that can only read.
CREATE USER IF NOT EXISTS 'foodease_report'@'localhost' IDENTIFIED BY 'ChangeThisReportPassword!1';
GRANT SELECT ON foodease.* TO 'foodease_report'@'localhost';

FLUSH PRIVILEGES;

-- Check what an account can do:
-- SHOW GRANTS FOR 'foodease_app'@'localhost';
