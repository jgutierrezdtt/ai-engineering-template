---
name: engineering-architecture
description: Diseña o cambia límites, datos y contratos públicos de la API, runtime y SDK del proyecto; úsala para decisiones de arquitectura y compatibilidad, sin imponer un stack.
---

# Arquitectura y contratos del proyecto

Leer el contexto del proyecto en README.md y las decisiones de arquitectura existentes. Antes de elegir herramientas,
especificar un flujo concreto del producto, los datos, los límites de
confianza y los efectos externos. Registrar las decisiones duraderas en el formato documental del proyecto.

## Límites que deben quedar resueltos

- Separar responsabilidades de control (identidad, planes, catálogo, políticas,
  cuotas) y ejecución (trabajos, herramientas, estado y resultados). Pueden
  desplegarse juntos al principio; separar procesos cuando el aislamiento o la carga lo exijan.
- Si existen una API alojada y un runtime desplegable por el cliente, compartir el
  núcleo donde corresponda. Definir configuración, actualización, datos que salen
  del entorno y operación sin el servicio de control disponible.
- Si existe SDK, definir si es cliente HTTP, runtime embebido o ambos con entradas distintas.
  Nunca ocultar llamadas de red, descarga de ejecutables o telemetría. No meter
  credenciales de servicio en un SDK distribuido o en el navegador.
- Si se admiten plugins o contenedores del cliente, definir sus amenazas: procesos o contenedores
  no son automáticamente una frontera suficiente para código arbitrario hostil.
  Elegir sandbox y aislamiento del host según el riesgo, antes de ofrecer esa capacidad.

## Contratos y datos

Diseñar esquema versionado antes de API/SDK: autenticación y scopes, tenant
derivado de identidad verificada, límites/tamaños, errores estables localizables,
paginación, timeout/cancelación y streaming con control de presión. Definir
idempotencia, semántica de reintentos y entrega de eventos; no prometer exactly-once
de un sistema distribuido. Hacer el cargo y las acciones irreversibles idempotentes.

El modelo de datos declara propiedad, clasificación, cifrado, región, retención y
borrado en almacenamiento primario, memoria, índices, cachés y backups. Probar
aislamiento en repositorios de datos, colas, URLs firmadas y objetos, no solo en UI.
Las migraciones son compatibles por etapas expand/contract y tienen recuperación
probada. Versionar contratos públicos con una política de soporte y deprecación.

## Decidir y validar

Comparar al menos la solución simple existente y una alternativa razonable cuando
la decisión importe. Evaluar mantenimiento, coste, latencia, descarga del SDK,
operación local/nube, soporte y supply chain. No crear interfaces para cada clase,
repositorios genéricos ni microservicios sin consumidor o límite real.

Usar dependencias hacia el dominio, adaptadores explícitos e inyección de las
capacidades que se simulan. Validar con contratos consumidor/proveedor, matriz
SDK/runtime/servidor, pruebas de concurrencia y compatibilidad de esquemas. No
permitir que un patrón o métrica de líneas sustituya una responsabilidad cohesionada.
