'use client';

/**
 * Wrapper para usar Google Material Icons
 * Todos los iconos se renderizan con la clase 'material-icons'
 */

interface IconWrapperProps {
  name: string; // Nombre del icono en Material Icons (sin espacios)
  size?: 'sm' | 'md' | 'lg' | 'xl'; // Tamaño del icono
  className?: string;
  filled?: boolean; // Si es true, usa material-icons-filled
}

const sizeMap = {
  sm: 'text-sm',    // 16px
  md: 'text-base',  // 20px
  lg: 'text-2xl',   // 24px
  xl: 'text-4xl',   // 36px
};

export default function IconWrapper({
  name,
  size = 'md',
  className = '',
  filled = false,
}: IconWrapperProps) {
  const iconClass = filled ? 'material-icons-filled' : 'material-icons';
  const sizeClass = sizeMap[size];

  return (
    <span className={`${iconClass} ${sizeClass} inline-flex items-center ${className}`}>
      {name}
    </span>
  );
}

/**
 * Mapa de equivalencias de Heroicons a Material Icons
 * Usa este objeto para reemplazar iconos
 */
export const iconMap = {
  // Navegación
  home: 'home',
  dashboard: 'dashboard',
  settings: 'settings',
  notifications: 'notifications',
  
  // Acciones
  plus: 'add',
  trash: 'delete',
  edit: 'edit',
  save: 'save',
  close: 'close',
  menu: 'menu',
  
  // Estado
  check: 'check',
  checkCircle: 'check_circle',
  xCircle: 'cancel',
  alert: 'warning',
  exclamation: 'error',
  
  // Datos/Gráficos
  chart: 'bar_chart',
  table: 'table_chart',
  clock: 'schedule',
  server: 'storage',
  
  // Utilidades
  gear: 'settings',
  wrench: 'build',
  flask: 'science',
  beaker: 'science',
  
  // Conectividad
  wifi: 'wifi',
  wifi_off: 'wifi_off',
  cloud: 'cloud',
  
  // Usuarios
  user: 'person',
  lock: 'lock',
  eye: 'visibility',
  
  // Direccionales
  chevronLeft: 'chevron_left',
  chevronRight: 'chevron_right',
  arrowLeft: 'arrow_back',
  arrowRight: 'arrow_forward',
  
  // Otros
  fire: 'local_fire_department',
  sparkles: 'auto_awesome',
  bell: 'notifications',
};
