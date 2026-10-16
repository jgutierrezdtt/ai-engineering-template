---
name: engineering-product-design
description: Diseña y verifica UI, UX, accesibilidad, textos localizados, rendimiento y descubrimiento web del proyecto; úsala en interfaces, contenidos públicos y recursos visuales del producto.
---

# Producto, accesibilidad y descubrimiento

Leer el flujo real y sus usuarios. Antes de construir, definir tarea principal,
arquitectura de información, estados y jerarquía visual; seguir el sistema de
diseño existente. Cuando aún no exista, proponer una dirección coherente y
verificable con tokens y un flujo representativo antes de extenderla.

## Diseño que ayuda a operar agentes

Evitar una cuadrícula indiferenciada de tarjetas. Elegir tablas, listas, cronología,
diagramas de ejecución, paneles de detalle o espacios abiertos según la tarea.
Tipografía y espaciado consistentes, densidad adecuada, información progresiva y
movimiento moderado con reduced-motion. Lo moderno debe mejorar comprensión y
control, no añadir efectos que dificulten usar el producto.

Hacer comprensibles identidad del agente, estado real, permisos, herramientas,
coste, fuentes cuando proceda y consecuencias de confirmar. Permitir cancelar,
recuperarse de errores y distinguir plan, ejecución y resultado. No fingir trabajo
ejecutado, disponibilidad o métricas. No usar lenguaje persuasivo que oculte acciones
sensibles ni imponer confirmaciones repetidas para actos ya autorizados.

## Accesibilidad e internacionalización

Objetivo técnico WCAG 2.2 AA en procesos y páginas completas. HTML semántico,
teclado, foco visible y restaurado, nombres y errores accesibles, contraste, zoom,
reflow y tamaño de objetivos conforme al criterio aplicable. Formularios con
etiquetas e instrucciones; no depender de color, hover o arrastrar. Estados de
streaming y tareas largas se anuncian sin saturar lectores de pantalla.

Automatizar auditorías como axe y E2E sobre flujos críticos; revisión manual con
teclado y lector de pantalla real. Una puntuación automática no certifica conformidad.
Validar cada librería de componentes por accesibilidad, mantenimiento, licencia,
dependencias y tamaño; no asumir que una librería «headless» cumple por sí sola.

Textos visibles, metadatos SEO, emails, validaciones, alt y aria-label se resuelven
desde catálogos versionados. IDs estables y pluralización/fechas/números según
locale; evitar concatenación de frases. Comprobar claves faltantes, fallback,
expansión de texto y RTL si se ofrece. Constantes técnicas y datos del usuario
no son textos a traducir. Prompts de agentes son recursos con versión independiente.

## Rendimiento y medios

Medir por ruta/dispositivo un presupuesto antes de añadir librerías: descarga JS,
CSS, fuentes, SDK y LCP/INP/CLS. Imágenes responsive con formatos eficientes,
dimensiones explícitas, compresión y lazy-load fuera de pantalla; priorizar la
imagen LCP. Fuentes locales con licencia y subconjuntos cuando convenga; evitar
CDNs, trackers y librerías externas innecesarios. Cargar capacidades pesadas bajo demanda.

## SEO y descubrimiento por IA

Contenido público útil y rastreable, HTML renderizado, URLs estables, canonical,
sitemap, metadatos/idiomas y datos estructurados fieles al contenido. Documentar
API/SDK con ejemplos ejecutables, versiones y límites. Separar áreas públicas de
consola privada: autenticación real protege datos; robots.txt no lo hace.

Consultar las guías primarias enlazadas en estándares. OAI-SearchBot y GPTBot
tienen fines distintos; proponer política explícita de búsqueda y entrenamiento
antes de publicar robots. Acceso de rastreadores no garantiza indexación o cita.
No presentar llms.txt, «GEO» o un schema especial como requisito universal de ChatGPT.
Una integración en ChatGPT es un producto/protocolo separado de ser descubrible.
