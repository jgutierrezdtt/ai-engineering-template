---
name: engineering-compliance
description: Delimita obligaciones y evidencia del proyecto por territorio, sector, datos y rol de IA; úsala al definir usos regulados, tratar datos personales o afirmar conformidad, sin certificar cumplimiento.
---

# Cumplimiento por perfiles

Definir el territorio, sector y uso real de cada proyecto. No existe una lista
única que autorice todos los usos. Leer el contexto del README y las fuentes de
`README.md#referencias-oficiales`; verificar el texto primario vigente antes de una
decisión legal y distinguir normas publicadas, borradores, acuerdos políticos y
fechas efectivas. No copiar calendarios de memoria.

## Definir el perfil antes de habilitar un uso

Registrar territorio/oferta, usuario B2B/B2C, sector, finalidad, datos y afectados,
rol del proyecto/cliente/proveedor y límites del agente. Clasificar por **uso concreto**,
no por llamar al producto «SaaS», «SDK» o «agente». Casos de salud, empleo,
crédito, menores, decisiones significativas o biometría necesitan evaluación propia
antes de lanzamiento. Una cláusula contractual no sustituye controles del sistema.

Evaluar RGPD/LOPDGDD, encargados/subencargados, base jurídica, minimización,
derechos, transferencias y residencia; DPIA cuando proceda. La región de la DB no
demuestra residencia si modelos, soporte, telemetría o backups cruzan fronteras.
Definir retención y borrado verificable sin eliminar auditoría que deba conservarse.

Para IA: determinar rol y obligaciones aplicables del AI Act, clasificación de
riesgo/finalidad, transparencia, alfabetización, supervisión humana y documentación
que corresponda. No declarar que usar un modelo de tercero traslada todas las
obligaciones, ni que toda plataforma de agentes es automáticamente de alto riesgo.

Para SDK/runtime distribuido evaluar CRA y obligaciones de vulnerabilidades,
actualizaciones y soporte según el producto. Para accesibilidad mapear WCAG 2.2 AA
como objetivo técnico a obligaciones aplicables (EAA, normativa nacional y versión
de EN 301 549 pertinente); no tratarlas como equivalentes automáticos.
ENS, DORA, NIS2 y requisitos de salud/finanzas se analizan por entidad, servicio,
contrato y jurisdicción, no se activan todos por defecto. Mercado global necesita
un registro por país/estado; no publicar «cumplimiento mundial».

## Evidencia y decisiones

Mantener una matriz por control: requisito primario/versionado, aplicabilidad y
motivo, responsable real, implementación, prueba/evidencia, brecha y estado.
Estados: pendiente, no aplicable justificado, implementado sin verificar, verificado.
No usar «certificado» salvo que exista certificado válido con alcance y fecha.
Las normas ISO 27001/27701/42001, gestión de riesgos IA y calidad/lifecycle pueden
orientar procesos o una certificación elegida; una skill no las acredita.

Ante incertidumbre que condicione un lanzamiento regulado, preparar el análisis
y las preguntas concretas para revisión profesional competente, dejando bloqueado
ese uso. Continuar trabajo independiente. La autorización de desarrollo no debe
interpretarse como autorización para procesar datos reales o lanzar un caso prohibido.
