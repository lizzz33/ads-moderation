CREATE TABLE IF NOT EXISTS public.account (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE  IF NOT EXISTS public.advertisement (
    item_id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL,
    is_verified_seller BOOLEAN DEFAULT FALSE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category INTEGER NOT NULL,
    images_qty INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.moderation_results (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_violation BOOLEAN,
    probability FLOAT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);