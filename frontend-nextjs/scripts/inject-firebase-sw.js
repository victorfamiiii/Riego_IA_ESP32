import fs from 'fs';
import path from 'path';

const swPath = path.join(__dirname, '../public/sw-custom.js');
const firebaseSWPath = path.join(__dirname, '../public/sw.js');

const swContent = fs.readFileSync(swPath, 'utf8');
const firebaseContent = fs.readFileSync(firebaseSWPath, 'utf8');

if (!swContent.includes('firebase-messaging-compat')) {
  fs.writeFileSync(swPath, firebaseContent + '\n\n' + swContent);
  console.log('[inject-firebase-sw] Firebase injected into sw-custom.js ✅');
} else {
  console.log('[inject-firebase-sw] Already injected, skipping');
}
