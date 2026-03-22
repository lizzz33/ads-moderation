import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = 'http://localhost:8003';
const HEADERS = { 'Content-Type': 'application/json' };
const errorRate = new Rate('errors');

// ID существующих открытых объявлений
const ITEM_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// Тестовый пользователь для получения токена
const TEST_USER = {
    name: 'Load Test User',
    login: 'test@example.com',
    password: 'qwerty123'
};

export const options = {
    stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '1m', target: 150 },
        { duration: '30s', target: 0 },
    ],
    thresholds: {
        http_req_failed: ['rate<0.1'],
        errors: ['rate<0.1'],
    },
};

// Создаём пользователя и получаем токен перед тестом
export function setup() {
    console.log('Setup: Creating test user...');
    const createRes = http.post(`${BASE_URL}/users/`, JSON.stringify({
        name: TEST_USER.name,
        login: TEST_USER.login,
        password: TEST_USER.password
    }), { headers: HEADERS });

    console.log(`Create user status: ${createRes.status}`);

    console.log('Setup: Getting token...');
    const loginRes = http.post(`${BASE_URL}/login`, JSON.stringify({
        login: TEST_USER.login,
        password: TEST_USER.password
    }), { headers: HEADERS });

    check(loginRes, { 'Get token 200': (r) => r.status === 200 });

    if (loginRes.status !== 200) {
        console.error('Failed to get token');
        return { token: null };
    }

    try {
        const token = loginRes.json('access_token');
        console.log(`Token obtained: ${token.substring(0, 20)}...`);
        return { token: token };
    } catch (e) {
        console.error(`Error parsing token: ${e}`);
        return { token: null };
    }
}

export default function (data) {
    const token = data.token;

    if (!token) {
        console.error('No token available');
        return;
    }

    const authHeaders = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };

    const r = Math.random();
    const id = ITEM_IDS[Math.floor(Math.random() * ITEM_IDS.length)];

    if (r < 0.4) {
        // GET /simple_predict - читаем существующие объявления
        const res = http.post(`${BASE_URL}/simple_predict`,
            JSON.stringify({ item_id: id }),
            { headers: authHeaders }
        );
        check(res, { 'simple_predict 200': (r) => r.status === 200 });
        errorRate.add(res.status !== 200);
    }
    else if (r < 0.7) {
        // POST /predict - создаем новые объявления
        const newId = Date.now() % 10000 + 1000;
        const res = http.post(`${BASE_URL}/predict`,
            JSON.stringify({
                seller_id: 1,
                is_verified_seller: true,
                item_id: newId,
                name: `Item ${newId}`,
                description: "test",
                category: 5,
                images_qty: 3
            }),
            { headers: authHeaders }
        );
        check(res, { 'predict 200': (r) => r.status === 200 });
        errorRate.add(res.status !== 200);
    }
    else {
        // POST /async_predict - асинхронные предсказания
        const res = http.post(`${BASE_URL}/async_predict`,
            JSON.stringify({ item_id: id }),
            { headers: authHeaders }
        );
        check(res, { 'async_predict 200': (r) => r.status === 200 });
        errorRate.add(res.status !== 200);
    }

    sleep(1);
}