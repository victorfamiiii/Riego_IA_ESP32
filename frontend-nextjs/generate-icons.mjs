import sharp from 'sharp';
import fs from 'fs';
import path from 'path';

// Configuración de los íconos a generar
const sizes = [
  { size: 192, name: 'icon-192x192.png' },
  { size: 512, name: 'icon-512x512.png' },
  { size: 180, name: 'apple-touch-icon.png' }, // Para iOS
  { size: 32, name: 'favicon-32x32.png' },
  { size: 16, name: 'favicon-16x16.png' },
];

// SVG del icono (base64 o string)
const svgIcon = `<svg width="512" height="512" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="gradient" x1="0" y1="0" x2="512" y2="512" gradientUnits="userSpaceOnUse">
      <stop stop-color="#4caf50"/>
      <stop offset="1" stop-color="#2e7d32"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="115" fill="url(#gradient)"/>
  <path d="M256 96C256 96 180 180 180 260C180 302.091 214.101 336 256 336C297.899 336 332 302.091 332 260C332 180 256 96 256 96Z" fill="white" opacity="0.95"/>
  <ellipse cx="200" cy="300" rx="60" ry="100" fill="white" opacity="0.9" transform="rotate(-30 200 300)"/>
  <ellipse cx="312" cy="300" rx="60" ry="100" fill="white" opacity="0.9" transform="rotate(30 312 300)"/>
  <circle cx="240" cy="240" r="15" fill="#4caf50" opacity="0.4"/>
  <circle cx="265" cy="270" r="10" fill="#4caf50" opacity="0.3"/>
</svg>`;

const publicDir = path.join(__dirname, 'public');

// Función para generar íconos
async function generateIcons() {
  console.log('🎨 Generando íconos PWA...\n');

  // Asegurar que el directorio public existe
  if (!fs.existsSync(publicDir)) {
    fs.mkdirSync(publicDir, { recursive: true });
  }

  // Convertir SVG a buffer
  const svgBuffer = Buffer.from(svgIcon);

  // Generar cada tamaño
  for (const { size, name } of sizes) {
    try {
      await sharp(svgBuffer)
        .resize(size, size)
        .png()
        .toFile(path.join(publicDir, name));
      
      console.log(`✅ ${name} (${size}x${size})`);
    } catch (error) {
      console.error(`❌ Error generando ${name}:`, error.message);
    }
  }

  // Copiar el de 32x32 como favicon.ico (simplificado)
  try {
    fs.copyFileSync(
      path.join(publicDir, 'favicon-32x32.png'),
      path.join(publicDir, 'favicon.ico')
    );
    console.log('✅ favicon.ico (copiado desde 32x32)');
  } catch (error) {
    console.error('❌ Error copiando favicon.ico:', error.message);
  }

  console.log('\n🎉 ¡Íconos generados exitosamente!');
  console.log('📁 Ubicación:', publicDir);
  console.log('\n📱 Archivos creados:');
  sizes.forEach(({ name, size }) => {
    console.log(`   - ${name} (${size}x${size}px)`);
  });
  console.log('   - favicon.ico');
}

// Ejecutar
generateIcons().catch(console.error);
