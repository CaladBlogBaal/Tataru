CREATE TABLE IF NOT EXISTS data_center (
    name text PRIMARY KEY,
    region varchar(2)
);

CREATE TABLE IF NOT EXISTS world (
    name text PRIMARY KEY,
    region varchar(2),
    dc_name text,
    FOREIGN KEY (dc_name) REFERENCES data_center (name)
);

CREATE TABLE IF NOT EXISTS users (
    user_id bigint PRIMARY KEY,
    name text NOT NULL
);


CREATE TABLE IF NOT EXISTS lodestone_user (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    lodestone_id bigint,
    PRIMARY KEY (user_id),
    first_name varchar(15),
    second_name varchar(15),
    world_name text,
    region varchar(2),
    FOREIGN KEY (world_name) REFERENCES world (name)

);

CREATE TABLE IF NOT EXISTS expansion (
    id SMALLSERIAL PRIMARY KEY,
    name text UNIQUE NOT NULL,
    patch_number smallint UNIQUE
);

CREATE TABLE IF NOT EXISTS bracket (
    min smallint PRIMARY KEY,
    expansion_name varchar(3),
    max real,
    FOREIGN KEY (expansion_name) REFERENCES expansion (name)
);

CREATE TABLE IF NOT EXISTS zone (
    id smallint PRIMARY KEY,
    name text,
    frozen boolean,
    expansion_name varchar(3),
    FOREIGN KEY (expansion_name) REFERENCES expansion (name)
);

CREATE TABLE IF NOT EXISTS difficulties (
    id SMALLSERIAL PRIMARY KEY,
    diff_id smallint,
    zone_id smallint,
    name varchar(9),
    FOREIGN KEY (zone_id) REFERENCES zone (id)
);

CREATE TABLE IF NOT EXISTS encounter (
   id smallint PRIMARY key,
   zone_id smallint,
   name text,
   alias_s varchar(4),
   alias_n varchar(4),
   expansion_name varchar(3),
   FOREIGN KEY (expansion_name) REFERENCES expansion (name),
   FOREIGN KEY (zone_id) REFERENCES zone (id)

);

CREATE TABLE IF NOT EXISTS gamerscape_images (
    id serial PRIMARY KEY,
    title text,
    name text UNIQUE,
    url text,
    description_url text,
    description_short_url text,
    timestamp timestamp

);

INSERT INTO expansion (name, patch_number) values('Ew', 6.0) ON CONFLICT DO NOTHING;
INSERT INTO expansion (name, patch_number) values('ShB', 5.0) ON CONFLICT DO NOTHING;
INSERT INTO expansion (name, patch_number) values('StB', 4.0) ON CONFLICT DO NOTHING;
INSERT INTO expansion (name, patch_number) values('Hw', 3.0) ON CONFLICT DO NOTHING;
INSERT INTO expansion (name, patch_number) values('ARR', 2.0) ON CONFLICT DO NOTHING;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS name_trgm_lower_idx ON gamerscape_images USING gin (LOWER(name) gin_trgm_ops);