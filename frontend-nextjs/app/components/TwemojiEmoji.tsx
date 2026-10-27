/**
 * Componente TwemojiEmoji
 * Renderiza emojis como SVG de Twemoji para consistencia visual en todos los sistemas
 */

import Image from 'next/image';

interface TwemojiEmojiProps {
  emoji: string;
  size?: number;
  className?: string;
  alt?: string;
}

export default function TwemojiEmoji({
  emoji,
  size = 24,
  className = '',
  alt = emoji,
}: TwemojiEmojiProps) {
  // Convertir emoji a código de punto Unicode
  const codePoint = [...emoji]
    .map((c) => c.codePointAt(0)!.toString(16).padStart(4, '0'))
    .filter((c) => c !== 'fe0f') // remover variante selector
    .join('-');

  return (
    <Image
      src={`https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/${codePoint}.svg`}
      alt={alt}
      width={size}
      height={size}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
      loading="lazy"
      className={className}
      unoptimized
    />
  );
}
