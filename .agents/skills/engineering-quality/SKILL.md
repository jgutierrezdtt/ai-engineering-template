---
name: engineering-quality
description: Selecciona, implementa y ejecuta pruebas de software, SDK, UI y agentes del proyecto con aislamiento, presupuestos y evidencia; úsala al cambiar comportamiento o controles de calidad.
---

# Calidad y pruebas

La fuente es `README.md#verificación-y-calidad` y su inventario ejecutable
`policy/quality.json`. Leer ambos. Elegir pruebas que puedan refutar el cambio;
no añadir pruebas que solo repitan la implementación ni tests nuevos para una
edición menor de texto. Un fallo real requiere regresión reproducible.

## Diseñar la comprobación

Mapear criterios de aceptación y riesgos a capas: unitarias/propiedades,
contratos/API/SDK, integración, E2E, a11y/visual, seguridad, agentes y operación.
Probar rutas de error, límites, concurrencia, cancelación y recuperación cuando se
afecten. Definir datos y oráculo independiente del resultado implementado. No
inventar porcentajes de cobertura o métricas que no se han ejecutado.

Quick: datos sintéticos, reloj/azar controlados, servicios simulados con contratos
verificados y sin red de pago; ejecutar dependencias afectadas y críticos transversales.
Release: conjunto completo, servicios efímeros, proveedor real acotado y navegadores
relevantes. Evals de agentes separan capacidad de invariantes de seguridad; una
media de calidad no compensa una fuga entre tenants. WER solo aplica si hay voz.

No marcar como éxito tests vacíos, skipped por herramienta ausente o snapshot
actualizado sin revisar. Flaky: aislar causa con evidencia y responsable/plazo;
no ocultar el defecto mediante reintentos ilimitados. Mantener baselines versionados
y revisar su modificación como cambio funcional.

## Estado y recursos

Usar `AIE_RUN_DIR` y run-id, nunca rutas globales ni datos de usuarios reales.
Cada recurso tiene dueño y cleanup idempotente; DB/colas/contenedores de cada run
usan namespace propio. Preparar finally y cleanup de CI, además de recolector por
TTL para caídas bruscas. Validar que fallar/cancelar una prueba limpia su estado y
que el siguiente run no hereda memoria. No limpiar con patrones globales destructivos.

Medir duración p50/p95, coste de evals y recursos. Mantener quick bajo 120 s mediante
selección segura y concurrencia limitada; si no cabe, informar y corregir el
cuello de botella sin quitar controles. Pruebas de carga/soak, recuperación,
seguridad extensa y evaluación estadística no se prometen en ese presupuesto.

## Cerrar

Comunicar comando real, alcance, resultado, duración y límites. Guardar evidencia
saneada según retención; no dejar informes brutos en Git ni transcripciones en prompts.
Conservar resultados saneados en `.artifacts/evidence/` o en el almacén autorizado
del proyecto, con versiones, alcance y huellas; establecer retención explícita.
Si una prueba o gate aún es un diseño, anotarlo como pendiente en el README o en el registro propio del proyecto.
Usar `tools/verify_change.py` para el perfil mínimo. Los tests de hooks comprueban
decisiones/protocolo; su cobertura real necesita pruebas del runtime con hook
ausente, error y timeout, según `README.md#activación-en-codex-y-claude-code`.
