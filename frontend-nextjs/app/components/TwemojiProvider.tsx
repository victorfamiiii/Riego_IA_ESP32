'use client';

import { useEffect } from 'react';
import twemoji from 'twemoji';

/**
 * Componente que aplica Twemoji a toda la aplicación
 * Convierte emojis de texto a imágenes SVG consistentes
 */
export default function TwemojiProvider() {
  useEffect(() => {
    // Aplicar Twemoji al documento completo
    twemoji.parse(document.documentElement, {
      folder: 'svg',
      ext: '.svg',
    });

    // Crear observer para nuevos elementos (para SPA)
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.addedNodes.length) {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // NODE_TYPE.ELEMENT_NODE
              twemoji.parse(node as HTMLElement, {
                folder: 'svg',
                ext: '.svg',
              });
            }
          });
        }
      });
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    return () => observer.disconnect();
  }, []);

  return null; // Este componente no renderiza nada visible
}
