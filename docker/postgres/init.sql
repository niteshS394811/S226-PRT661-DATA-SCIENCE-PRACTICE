CREATE DATABASE nemdb;

CREATE USER nemuser WITH PASSWORD 'nempassword';

GRANT ALL PRIVILEGES ON DATABASE nemdb TO nemuser;

\connect nemdb
GRANT ALL ON SCHEMA public TO nemuser;