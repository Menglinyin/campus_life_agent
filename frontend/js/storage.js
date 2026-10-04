import {validId} from './api.js';
export async function identityKey(token) {
  if (!globalThis.crypto?.subtle) return null;
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  return 'campus.sessions.' + Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,32);
}
export function readSessions(key, storage) {
  if (!key) return [];
  try { const target=storage ?? globalThis.localStorage; const rows = JSON.parse(target.getItem(key) || '[]'); return Array.isArray(rows) ? rows.filter(x=>validId(x?.id) && Number.isFinite(x.updated)).slice(0,30) : []; } catch { return []; }
}
export function saveSessions(key, rows, storage) {
  if (!key) return;
  try { const target=storage ?? globalThis.localStorage; target.setItem(key, JSON.stringify(rows.map(({id,updated})=>({id,updated})).slice(0,30))); } catch { /* Private browsing/storage quota: in-memory session still works. */ }
}
