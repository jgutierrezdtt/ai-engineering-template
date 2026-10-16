---
name: engineering-security
description: Aplica controles de seguridad al modificar identidad, tenants, datos, secretos, red, SDK o dependencias del proyecto; no sustituye una auditoría de seguridad solicitada expresamente.
---

# Seguridad de aplicación y cadena de suministro

Identificar activos, actores y límites de confianza afectados. Elegir controles
aplicables de ASVS con versión e identificador exactos; consultar
`README.md#referencias-oficiales`. No inventar IDs ni afirmar certificación OWASP.
Registrar amenazas nuevas en el ADR o diseño afectado; un cambio rutinario no
obliga a una auditoría completa. Leer la skill de agentes si cambia su capacidad.

## Decisiones de implementación

- Identidad verificada; autorización deny-by-default en servidor por acción y
  recurso; tenant tomado del contexto autenticado y contrastado en cada almacén.
  Probar usuarios/roles/tenants contrarios, incluido admin y soporte.
- Secretos por gestor e identidad de carga, scopes/TTL mínimos y rotación diseñada.
  Sin claves de plataforma distribuidas. Autenticación de API/SDK según entorno;
  credenciales de navegador limitadas y temporales, nunca un secreto permanente.
- Sesiones/cookies seguras, CSRF según arquitectura, CORS explícito, límites de
  solicitudes y de cuerpos, consultas parametrizadas, codificación de salida,
  CSP adecuada y validación de archivos. La autorización no depende de CORS o UI.
- TLS validado; gestión automática de certificados y alerta de expiración.
  mTLS por riesgo. Callbacks/webhooks autenticados, con vigencia y anti-replay,
  y destinos validados contra SSRF/redirecciones/DNS rebinding.
- Contenedores sin root, capacidades mínimas, filesystem de solo lectura donde
  proceda, volúmenes acotados y seccomp/sandbox. Red saliente restringida; no montar
  socket Docker ni credenciales del host en ejecuciones de clientes.
- Logs estructurados con allowlist de campos; omitir tokens, PII, prompts y salidas
  completas por defecto. Auditar acciones privilegiadas sin almacenar secretos.

## Dependencias, SDK y distribución

Antes de incorporar una dependencia: necesidad frente a plataforma nativa,
procedencia/mantenedor, soporte, vulnerabilidades actuales, licencia, transitivas,
tamaño real de descarga/ejecución y permisos de instalación. No introducir un paquete
por una función trivial ni reimplementar criptografía para ahorrar dependencias.
No confundir fecha reciente con seguridad.

Lockfiles versionados y build determinista con instalación frozen; herramientas
por versión/hash, imágenes por digest, acciones por SHA. Revisar scripts de
instalación y ejecutar solo los necesarios. Actualizaciones verificadas con PR y
pruebas, no versiones flotantes. Generar inventario/SBOM y provenance para releases.
Firmar y **verificar** identidad del emisor, digest, repositorio y workflow esperado
al consumir paquetes/runtime. Certificados y firmas prueban procedencia, no ausencia de fallos.

Definir presupuesto de descarga y dependencias del SDK tras medir un prototipo;
árbol de dependencias mínimo, entradas separadas y carga opcional de capacidades.
Prohibir autoactualizaciones o ejecución remota oculta. Mantener política de soporte,
avisos y remediación de vulnerabilidades con contactos reales al establecerlos.

## Verificación e incidentes

Ejecutar scanner de secretos y controles de stack pertinentes. Probar aislamiento,
permisos negativos, abuso de entradas y egress; añadir SAST/SCA/IaC/contenedores y
DAST en entorno autorizado al conectar el producto. Seguir el bloqueo y las
excepciones del contrato de calidad. Ante secreto expuesto seguir
`README.md#git-y-secretos`; nunca imprimirlo ni simplemente recortarlo.

Para reforzar al agente de desarrollo leer `README.md#activación-en-codex-y-claude-code`.
Probar rutas alternativas y errores del hook; un filtro de shell, hash de contexto
o archivo editable por la misma IA no constituye una frontera de seguridad.
