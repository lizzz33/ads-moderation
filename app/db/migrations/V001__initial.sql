DROP TABLE IF EXISTS public.account CASCADE;
DROP TABLE IF EXISTS public.sellers CASCADE;
DROP TABLE IF EXISTS public.advertisement CASCADE;
DROP TABLE IF EXISTS public.moderation_results CASCADE;

CREATE TABLE IF NOT EXISTS public.account (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.sellers (
    seller_id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE  IF NOT EXISTS public.advertisement (
    item_id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category INTEGER NOT NULL CHECK (category >= 0 AND category <= 100),
    images_qty INTEGER DEFAULT 0 CHECK (images_qty >= 0 AND images_qty <= 10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id) ON DELETE CASCADE
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

ALTER TABLE moderation_results 
ADD CONSTRAINT fk_moderation_results_ads 
FOREIGN KEY (item_id) REFERENCES advertisement(item_id) ON DELETE CASCADE;