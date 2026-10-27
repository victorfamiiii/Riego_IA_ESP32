import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const swPath = path.join(__dirname, '../public/sw-custom.js');
const firebaseSWPath = path.join(__dirname, '../public/sw.js');

const swContent = fs.readFileSync(swPath, 'utf8');
const firebaseContent = fs.readFileSync(firebaseSWPath, 'utf8');

if (!swContent.includes('firebase-messaging-compat')) {
  fs.writeFileSync(swPath, `${firebaseContent}\n\n${swContent}`);
  console.warn('[inject-firebase-sw] Firebase injected into sw-custom.js ✅');
} else {
  console.warn('[inject-firebase-sw] Already injected, skipping');
}