// Dev-only Vite plugin: serves the CyberHero API from JSON fixtures so the
// front-end can be developed without a running Flask backend.
//
//   npm run dev:mock
//
// Fixtures live in mock/fixtures/ and are generated from the real backend:
//   python scripts/dump_cyberhero_fixtures.py   (repo root)
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(here, 'fixtures');
const API_PREFIX = '/api/v1/cyberhero/';
const FONTS = join(here, '..', '..', 'app', 'static', 'fonts');

function send(res, status, payload) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(payload));
}

function readFixture(name) {
  const file = join(FIXTURES, `${name.replace(/\//g, '__')}.json`);
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, 'utf8'));
}

function readBody(req) {
  return new Promise((resolve) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
    });
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        resolve({});
      }
    });
  });
}

export function mockApiPlugin() {
  const issued = new Map();
  return {
    name: 'cyberhero-mock-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url, 'http://localhost');
        if (url.pathname === '/api/v1/auth/csrf') return send(res, 200, { csrf_token: 'mock-csrf' });
        if (url.pathname.startsWith('/static/fonts/')) {
          const file = join(FONTS, url.pathname.replace('/static/fonts/', ''));
          if (existsSync(file)) {
            res.setHeader('Content-Type', 'font/woff2');
            return res.end(readFileSync(file));
          }
        }
        if (!url.pathname.startsWith(API_PREFIX)) return next();
        const path = url.pathname.slice(API_PREFIX.length).replace(/\/+$/, '');

        if (path === 'progress') return send(res, 401, { error: { code: 401, message: 'Authentication required' } });
        if (path === 'certificates' && req.method === 'POST') {
          const body = await readBody(req);
          const name = String(body.display_name || '').trim();
          if (name.length < 2) return send(res, 400, { error: { code: 400, message: 'Please enter the name to print on the certificate.' } });
          const id = `CH-${new Date().getFullYear()}-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
          const cert = {
            public_id: id,
            valid: true,
            display_name: name,
            track: body.track || 'guardians',
            track_name: { en: 'Cyber Guardians', ka: 'კიბერ დამცველები' },
            points: 0,
            max_points: 0,
            issued_at: new Date().toISOString(),
            verify_url: `/certificates/verify/${id}`,
          };
          issued.set(id, cert);
          return send(res, 201, cert);
        }
        if (path.startsWith('certificates/')) {
          const id = path.slice('certificates/'.length).toUpperCase();
          const cert = issued.get(id);
          return cert ? send(res, 200, cert) : send(res, 404, { valid: false, public_id: id });
        }

        const data = readFixture(path);
        if (!data) return send(res, 404, { error: { code: 404, message: `No fixture for ${path}` } });
        // list endpoints accept the same filters as the real API
        const filter = url.searchParams.get('track') || url.searchParams.get('shelf');
        if (filter && Array.isArray(data.items)) {
          const key = url.searchParams.get('track') ? 'track' : 'shelf';
          return send(res, 200, { ...data, items: data.items.filter((item) => String(item[key]).toLowerCase() === filter.toLowerCase()) });
        }
        return send(res, 200, data);
      });
    },
  };
}
