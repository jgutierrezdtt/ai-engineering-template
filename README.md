# AI Engineering Template

[![Verificación](https://github.com/jgutierrezdtt/ai-engineering-template/actions/workflows/foundation.yml/badge.svg)](https://github.com/jgutierrezdtt/ai-engineering-template/actions/workflows/foundation.yml)

Plantilla de repositorio para desarrollar con **Codex y Claude Code** usando reglas
compartidas, skills especializadas y controles ejecutables. Incluye seguridad,
arquitectura, calidad, agentes de IA, DevOps, diseño, accesibilidad y cumplimiento
según el alcance de cada proyecto. No impone lenguaje, framework ni nube.

**Este repositorio es una base de ingeniería, no una aplicación ni una certificación.**
Las instrucciones orientan al agente; los hooks interceptan herramientas compatibles;
el aislamiento y las protecciones del servidor restringen operaciones concretas.
Ninguna plantilla garantiza obediencia absoluta, ausencia de defectos o conformidad
universal. La sección de límites explica qué se comprueba.

La guía humana está en este README. Los archivos `AGENTS.md`, `CLAUDE.md` y
`SKILL.md` son instrucciones que consumen las herramientas. No se incluyen expedientes,
informes ni evidencias heredados de otro proyecto. Licencia [MIT](LICENSE).

## Crear un proyecto

1. Pulsa [Use this template](https://github.com/jgutierrezdtt/ai-engineering-template/generate)
   y elige propietario, nombre y visibilidad del nuevo proyecto.
2. Clona **el repositorio nuevo**. La generación crea un historial independiente;
   no conecta el producto con el historial de esta plantilla.
3. Revisa `AGENTS.md`, las skills y los scripts antes de confiar en ellos. Necesitas
   Git, Python 3.9 o posterior y Gitleaks 8.30.1. Las pruebas con CLI nativos necesitan
   Docker y descarga inicial de herramientas verificadas; no necesitan claves de modelos.
4. Activa el hook local y comprueba la base desde la raíz del proyecto:

```sh
git config --local core.hooksPath .githooks
python3 -B tools/sync_skills.py --check
python3 -B tools/verify_change.py
```

Si falta el scanner, `python3 -B tools/bootstrap_scanner.py --directory .artifacts/scanner`
descarga la versión fijada y verifica su huella. Añade ese directorio al PATH **de la
sesión**, sin reemplazar otras entradas. No se omite el control cuando falta una herramienta.

5. Completa el contexto del producto, sus comandos de calidad y las decisiones que
   se describen a continuación. Abre una sesión nueva de Codex o Claude Code en la
   raíz del repositorio y comprueba su activación.
6. Permite la primera ejecución de Actions y activa las protecciones de GitHub.
   **Los ajustes del servidor y la configuración local de Git no se heredan al generar
   un repositorio desde la plantilla.** Cada proyecto necesita este paso.

Al adoptar la plantilla en un repositorio existente, integra los archivos mediante
una rama revisable. No sobrescribas reglas, hooks, workflows o skills existentes.

## Configurar nuestras reglas

| Archivo | Qué se configura |
| --- | --- |
| `AGENTS.md` | Acuerdos comunes y selección de procedimientos; fuente principal de reglas. |
| `CLAUDE.md` | Importa `AGENTS.md` para Claude Code; evita mantener otra política divergente. |
| `.agents/skills/<nombre>/SKILL.md` | Procedimientos canónicos por disciplina, con nombre y descripción de activación. |
| `.claude/skills/<nombre>/SKILL.md` | Copias generadas para el descubrimiento de skills de Claude Code. |
| `policy/agent-enforcement.json` | Directorios editables, comandos admitidos, límite de contexto y versiones de referencia. |
| `policy/adapters/` | Eventos y configuración de hooks de cada proveedor. |
| `policy/quality.json` | Comandos reales de pruebas, perfiles, concurrencia y presupuestos. |
| `policy/targets.json` | Datos que deben concretarse antes de publicar el futuro producto. |
| `policy/*toolchain.json`, `policy/verification-tools.json` | Versiones, orígenes e integridad de las herramientas descargadas. |

En cada proyecto, sustituye este bloque por su contexto real: **objetivo y primer
flujo, usuarios, datos, acciones permitidas, territorios, stack, organización,
comandos, entornos y responsables**. Actualiza también los enlaces y la insignia del
README para que apunten al nuevo repositorio. Elegir una nube o un framework es una
decisión del proyecto, no un requisito de esta plantilla.

Las ocho skills cubren entrega, arquitectura, seguridad, calidad, agentes, DevOps,
diseño y cumplimiento. Las reglas compartidas permanecen en `AGENTS.md`; no copiar
todo ese archivo en cada skill. Después de editar una skill canónica, ejecuta:

```sh
python3 -B tools/sync_skills.py
python3 -B tools/check_repository.py
```

El verificador rechaza copias divergentes. Para añadir otra skill, crea su carpeta
con `SKILL.md`, frontmatter `name`/`description`, instrucciones acotadas y recursos
solo cuando aporten valor. Actualiza el inventario `SKILLS` de
`tools/check_repository.py`, la matriz de selección, el generador y las pruebas
nativas que comprueban el contexto. Prueba una petición representativa y un fallo
relevante; validar el formato no demuestra que la IA tome buenas decisiones.

## Activación en Codex y Claude Code

| Entorno | Carga de instrucciones | Activación de controles |
| --- | --- | --- |
| Codex local, CLI o entorno compatible | `AGENTS.md` y `.agents/skills/` dentro del proyecto. | Adaptador en `.codex/hooks.json`; función hooks y confianza revisadas en la sesión. |
| Claude Code | `CLAUDE.md` importa las reglas; `.claude/skills/` ofrece las skills. | Hooks en `.claude/settings.json`, tras revisión y confianza del proyecto. |
| Codex Cloud u otro entorno remoto | Incluir los archivos en el checkout y preparar herramientas en el entorno. | Ejecutar la misma validación en CI; verificar soporte de hooks y aislamiento allí. No asumir soporte idéntico al CLI. |
| Otro editor, ChatGPT o una API de modelos | Integración explícita que cargue las reglas como instrucciones y conecte las herramientas controladas. | El modelo o un chat no leen automáticamente el repositorio ni ejecutan estas políticas. Se necesita un adaptador probado. |

Se distribuyen adaptadores de proyecto, sin modificar configuración global ni
conceder confianza automáticamente. El perfil de hooks es **restrictivo**: admite
lecturas concretas, edición en las áreas declaradas y los comandos exactos de
validación. Deniega comandos de shell arbitrarios, conectores desconocidos y
cambios de reglas. Es intencionado: el mantenedor debe preparar dependencias y
capacidades necesarias desde su entorno de control antes de la ejecución del agente.

Comprobación básica sin iniciar un modelo:

```sh
python3 -B tools/check_agent_setup.py codex
python3 -B tools/check_agent_setup.py claude
```

Referencia de compatibilidad ensayada: **Codex 0.160.1 y Claude Code 2.1.295**.
Una versión distinta necesita su propia comprobación; las herramientas no se
actualizan globalmente. `python3 -B tools/project_toolchain.py install-claude`
prepara Claude en el ámbito del proyecto con integridad verificada, cuando la
plataforma está declarada. Después, `tools/launch_agent.py` resuelve esa instalación.

El lanzador carga el adaptador de forma explícita para reducir la dependencia del
descubrimiento de configuración. Conserva permisos y confianza nativos; iniciar
una sesión real requiere la cuenta o credenciales propias del proveedor:

```sh
python3 -B tools/launch_agent.py codex
python3 -B tools/launch_agent.py claude
```

Revisa en la herramienta los hooks activos. Solicitar un resumen de las reglas
ayuda a diagnosticar contexto, pero **no es evidencia suficiente de bloqueo**.
La comprobación automatizada de comportamiento se ejecuta así:

```sh
python3 -B tools/bootstrap_native.py
python3 -B tools/run_native_container.py --output .artifacts/native-report.json
```

Son 14 escenarios: acción permitida, denegada, hook ausente, error, JSON inválido,
timeout y frontera externa, para ambos CLI. Se usan los ejecutables reales con
respuestas sintéticas servidas en loopback; no se evalúan modelos comerciales ni
se consumen tokens de pago. La suite comprueba contexto completo, callbacks y
efectos observables. El contenedor usa Linux ARM64, usuario 10001, red externa
desactivada, raíz y controles de solo lectura, límites de CPU/memoria/procesos y
retirada al finalizar. En equipos de otra arquitectura puede necesitar emulación.

**Límite observado:** en la versión de Codex ensayada, un hook que falla puede
dejar continuar una herramienta. Esos casos pasan la prueba si reproducen ese
comportamiento esperado; no significan que el hook haya bloqueado. La prueba de
frontera externa comprueba por separado que los controles no puedan sobrescribirse.
Los resultados nuevos están en Actions o en los artefactos locales de cada ejecución.

## Verificación y calidad

| Perfil | Alcance y aceptación |
| --- | --- |
| `bootstrap` | Estructura, instrucciones, secretos y pruebas de las herramientas de la plantilla. |
| `quick` | Base y controles incrementales del producto; presupuesto predeterminado de 120 segundos. |
| `release` | Base, quick y verificaciones de publicación; presupuesto predeterminado de 1800 segundos. |

La plantilla deja los controles de producto **sin comando** deliberadamente.
`quick` y `release` fallan con salida 2 hasta configurarlos. Al aparecer directorios
como `src`, `apps`, `packages`, `agents` o manifiestos de producto, el selector
exige quick. Revisa `tools/verify_change.py` si el stack usa otra organización;
el selector es una convención verificable, no un clasificador universal de código.

Cada `command` es una lista de argumentos, por ejemplo `['npm', 'run', 'lint']`
(en JSON se usan comillas dobles). Conecta pruebas reales y presupuestadas de
tipos/lint, unidades/contratos, agentes, UI/i18n/accesibilidad y dependencias; amplía
release con integración/E2E, proveedor real, seguridad, recuperación y procedencia.
Adapta la aplicabilidad al producto con motivo documentado. WER aplica si hay voz;
una librería sin UI no necesita inventar una prueba de navegador.

No usar comandos de éxito vacío, reducir expectativas ni eliminar un control
porque falla. El orquestador rechaza inventarios vacíos, configuración incompleta,
errores y presupuestos inválidos. Cada control recibe su propio `AIE_RUN_DIR`,
que se retira al finalizar; los descendientes se terminan tras timeout. Estas
medidas no convierten el orquestador ordinario en un sandbox para código hostil.

### Verificar propuestas desde una referencia confiable

Mantén el repositorio de controles fuera del área de escritura del agente. Desde
esa copia confiable, exporta la versión aprobada a un directorio nuevo:

```sh
python3 -B tools/managed_workspace.py --export /ruta/nueva/candidato
python3 -B tools/verify_candidate.py /ruta/nueva/candidato --reference HEAD
```

El candidato debe ser una exportación de fuentes sin `.git`, dependencias ni
estado local. Se congela, se rechazan enlaces y archivos especiales, se comparan
controles con la referencia y se ejecutan las verificaciones de producto bajo
aislamiento. Crear directorios editables requiere una preparación revisada de la
referencia. `python3 -B tools/managed_workspace.py -- /bin/pwd` prueba una ejecución
efímera; su salida JSON resume condiciones y resultado.

El backend local de macOS utiliza Seatbelt. Linux exige Bubblewrap; si falta o no
funciona, se rechaza la ejecución y no se utiliza una alternativa sin aislamiento.
La CI macOS comprueba los efectos del backend macOS; la suite nativa comprueba el
contenedor Linux. Eso no acredita por sí solo el backend Bubblewrap de cada host.
Windows no dispone de backend en esta versión. No usar esta base como servicio
de ejecución de código hostil de clientes sin un diseño específico y revisión.

`tools/record_verification.py` permite recoger resultados saneados en un directorio
nuevo dentro de `.artifacts/evidence/`; no incorpora esos registros al template.
Su plan está diseñado para la base sin producto: verifica también que quick/release
permanezcan bloqueados. Adapta ese plan al crear una aplicación. Las huellas
detectan diferencias respecto de una referencia; no son firma ni revisión independiente.

## Git y secretos

El hook local analiza el contenido preparado para guardar y vuelve a comprobar el
perfil requerido. Usar ramas cortas y commits pequeños, con archivos explícitos y
autor real ya configurado. No confundir un commit local con subir código a Internet.
Git no copia automáticamente `core.hooksPath` al clonar o generar un repositorio.

Gitleaks está fijado por versión, con un secreto sintético de comprobación para
detectar scanners que no funcionan. Se revisan árbol, índice o historial según
el modo. También se bloquean nombres sensibles aunque su contenido no coincida con
un patrón conocido. `.gitignore` ayuda a evitar inclusión accidental; no revoca
secretos ni protege archivos ya guardados. El scanner no reconoce todos los secretos.

Si aparece un secreto: detener su inclusión, evitar imprimirlo, determinar si se
expuso y solicitar o ejecutar su revocación según autorización. Limpiar referencias
y revisar logs/artefactos afectados. No recortar una clave como solución ni reescribir
historial ajeno automáticamente. Para comunicar una vulnerabilidad, usar los canales
privados del propietario; no publicar credenciales o datos personales en issues.

## Protecciones de GitHub

El workflow `foundation` ejecuta `bootstrap` en macOS y `native-hooks` en Linux ARM64.
Usa Actions fijadas por SHA, token con lectura de contenido, checkout sin credenciales
persistentes y entornos temporales. No despliega ni recibe secretos de producción.
Los resultados saneados por caso y las observaciones nativas se retienen como
artefactos de Actions durante 30 días; no incluyen prompts ni mensajes de excepción.

Después de que ambos jobs terminen correctamente en la rama principal, con GitHub CLI
autenticada y permiso de administración, revisa y aplica el conjunto de reglas:

```sh
python3 -B tools/configure_github.py PROPIETARIO/REPOSITORIO
python3 -B tools/configure_github.py PROPIETARIO/REPOSITORIO --apply
```

El primer comando solo muestra la propuesta. El segundo configura la rama principal
con PR obligatorio, **una aprobación de otra persona**, resolución de conversaciones,
historial lineal, prohibición de borrado/force-push y ambos checks obligatorios ligados
a la aplicación GitHub Actions observada. No declara excepciones para administradores.
Se necesita otra persona con permiso de revisión: GitHub no permite aprobar el propio
PR. La aplicación de la regla se lee de nuevo desde el servidor antes de declararla activa.

Los permisos y funcionalidades disponibles dependen de la cuenta y plan de GitHub.
El script no puede impedir que un administrador autorizado cambie después las reglas.
Las credenciales que modifican el servidor deben permanecer fuera del entorno del
agente de producto. Un workflow revisable por la misma persona que fusiona no
equivale a una cadena de confianza independiente.

## Flujo de trabajo

Petición → criterios de aceptación → skills pertinentes → implementación →
verificación del perfil requerido → revisión de cambios y secretos → commit local
→ PR y CI → aprobación → publicación autorizada.

Los cambios de política o de herramientas siguen una revisión propia desde el
entorno de control. La política restrictiva deniega su modificación al agente de
producto; no concede una excepción implícita para resolver un bloqueo.

Para releases del futuro producto: construir una vez, promover el mismo artefacto,
generar inventario/SBOM y procedencia, firmar y verificar la identidad esperada,
probar el SDK si existe y ensayar recuperación. Elegir despliegue gestionado,
contenedores, canary u otra estrategia según riesgo, coste y datos reales.
`tools/source_bundle.py` solo genera un archivo reproducible de fuentes de ingeniería;
no es una release firmada de producto. `tools/readiness.py` es un diagnóstico de
pendientes de esta base y siempre rechaza declarar producción lista.

## Documentación de cada proyecto

Mantener README, instrucciones y pruebas durante el trabajo. Explicar propósito,
organización, configuración, decisiones, operación, comprobaciones y limitaciones.
Si el proyecto crece, acordar su documentación adicional sin arrastrar expedientes
de otro producto. No copiar conversaciones como memoria del repositorio.

Una prueba debe indicar entradas, resultado esperado, resultado observado y alcance.
Usar UTC en registros de máquina y explicar la hora local en informes para personas.
Un commit identifica una versión guardada; un hash comprueba coincidencia con una
referencia; un identificador interno organiza un registro. Ninguno acredita una
certificación. No inventar revisores, aprobaciones, fechas ni ejecuciones.

## Referencias oficiales

Consultar las fuentes vigentes antes de cambiar versiones, protocolos o tomar
decisiones normativas. Esta lista es una ruta de consulta, no una afirmación de conformidad:

- [Codex: instrucciones AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
  [skills](https://learn.chatgpt.com/docs/build-skills) y [hooks](https://learn.chatgpt.com/docs/hooks).
- [Claude Code: memoria e instrucciones](https://code.claude.com/docs/en/memory),
  [skills](https://code.claude.com/docs/en/skills) y [hooks](https://code.claude.com/docs/en/hooks).
- [GitHub: repositorios plantilla](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository)
  y [reglas de repositorio](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets).
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
  [seguridad de aplicaciones con IA](https://genai.owasp.org/),
  [NIST SSDF](https://csrc.nist.gov/projects/ssdf) y [SLSA](https://slsa.dev/).
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [MCP](https://modelcontextprotocol.io/specification/)
  y [A2A](https://a2a-protocol.org/latest/specification/).
- [RGPD](https://eur-lex.europa.eu/eli/reg/2016/679/oj) y
  [Reglamento de IA de la UE](https://eur-lex.europa.eu/eli/reg/2024/1689/oj), cuando sean aplicables.

Las condiciones de uso y distribución de los CLI descargados son las de sus
proveedores; la licencia MIT de esta plantilla no las sustituye. Los binarios y
las credenciales no se distribuyen en el repositorio.
