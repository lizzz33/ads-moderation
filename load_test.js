import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = 'http://localhost:8003';
const HEADERS = { 'Content-Type': 'application/json' };
const errorRate = new Rate('errors');

// ID существующих открытых объявлений
const ITEM_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

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

export default function () {
    const r = Math.random();
    const id = ITEM_IDS[Math.floor(Math.random() * ITEM_IDS.length)];

    if (r < 0.4) {
        // GET /simple_predict - читаем существующие объявления
        const res = http.post(`${BASE_URL}/simple_predict`,
            JSON.stringify({ item_id: id }),
            { headers: HEADERS }
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
            { headers: HEADERS }
        );
        check(res, { 'predict 200': (r) => r.status === 200 });
        errorRate.add(res.status !== 200);
    }
    else {
        // POST /async_predict - асинхронные предсказания
        const res = http.post(`${BASE_URL}/async_predict`,
            JSON.stringify({ item_id: id }),
            { headers: HEADERS }
        );
        check(res, { 'async_predict 200': (r) => r.status === 200 });
        errorRate.add(res.status !== 200);
    }

    sleep(1);
}