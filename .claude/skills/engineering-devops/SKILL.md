---
name: engineering-devops
description: Diseña o modifica builds, CI/CD, infraestructura, releases y recuperación del proyecto en local o nube; úsala para empaquetar o desplegar con evidencia y autorización del destino.
---

# DevOps, releases y operación

Leer las decisiones de arquitectura y las secciones de calidad y Git del README. Identificar destino, permisos,
coste, datos y autorización vigente. Preparar y verificar cambios reversibles
antes de pedir una autorización que realmente falte. No considerar esta skill
permiso para publicar, gastar, enviar código o modificar infraestructura externa.

## Local y CI con el mismo contrato

Ofrecer una interfaz de comandos coherente para bootstrap/quick/release; las
dependencias, versiones, config y recursos deben estar declarados. Contenedores
reproducibles y entornos efímeros cuando sirvan al aislamiento; no exigir Docker
para cada comando de edición ni Kubernetes para operar un único servicio.

CI con permisos mínimos por job, acciones por SHA y herramientas por hash;
sin credenciales de producción en PRs y sin ejecutar código no confiable con
`pull_request_target` privilegiado. Separar build/test de firma/publicación;
identidad OIDC restringida a repositorio/ref/workflow/entorno. No guardar secretos
en caché. Runners persistentes necesitan aislamiento, limpieza y reconciliación.
Cancelar ejecuciones obsoletas de validación; no cancelar una migración/publicación
activa sin un protocolo seguro. Timeout y conjunto vacío fallan.

## Artefacto y despliegue

Construir una vez y promover el mismo digest entre entornos. Generar SBOM,
provenance, firma y verificaciones del consumidor, paquetes SDK probados y matriz
de compatibilidad. Versionado semántico, changelog útil, deprecaciones y política
de soporte. No reconstruir el artefacto para producción con dependencias flotantes.

Comparar plataforma gestionada, contenedores o infraestructura propia según coste,
región, aislamiento, carga, soporte y salida del proveedor. Registrar ADR y plan
de costes antes de comprometer una nube. No crear certificados o permisos
globales sin necesidad; automatizar renovación y expiración verificables.

Elegir rolling/canary/blue-green según riesgo, capacidad y coste. Readiness/liveness
reales, drenaje de peticiones, cancelación y colas, migraciones expand/contract y
preservación de estado. Healthcheck verde no es validación de negocio. Ejecutar
smoke con permisos acotados tras desplegar y revertir por umbrales definidos.
Un rollback de binario no revierte necesariamente datos, cobros o efectos de agentes.

## Operación y evidencia

Definir SLO, p95, tasa de error, coste por tarea y cuotas por tenant, alertas y
responsable antes de producción. Propagar trace-id con campos saneados y no
registrar prompts por defecto. Probar restauración de backups, RPO/RTO, rotación
propia y un runbook de incidentes. Etiquetar recursos de pruebas por run-id/TTL y
recolectarlos automáticamente sin borrar recursos compartidos.

La meta de 1–2 minutos corresponde a feedback incremental medido y, si el
entorno lo permite, despliegue incremental precalentado. No prometer ese tiempo
para aprovisionamiento frío, restauraciones, auditorías ni suite completa.
Al terminar distinguir configuración entregada, ejecución comprobada y servicios pendientes.

Para agentes de desarrollo aplicar `README.md#activación-en-codex-y-claude-code`: hooks
de proyecto no son autoridad de publicación. Verificador, políticas, credenciales
y ajustes administrados deben quedar fuera de la escritura del agente para imponerla.
