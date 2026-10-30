# Revisión de `metodologia.md` — diagnóstico, justificación y cambios

Documento de respaldo de la revisión hecha sobre `metodologia.md` a partir de las observaciones de la tutora. Sirve para explicar en la defensa **por qué** el documento quedó así y **qué** se cambió respecto de la versión anterior.

---

## 1. Punto de partida: la observación de la tutora

La retroalimentación recibida fue:

> «Estas actividad no era buscar conceptos teóricos. Era que tenían que llevar a la práctica la planificación. Definición de las pruebas a usar (nombrarlas y por qué se usan). Pasos a realizar una auditoría, nombrar como un cronograma de actividades. Y los tipos de datos de las pruebas que usarán.»

De ahí se desprenden cuatro exigencias concretas:

| Exigencia | Qué implica |
|---|---|
| Llevar la planificación a la práctica | El documento debe describir **este** sistema y **este** encargo, no la teoría general de pruebas |
| Nombrar las pruebas y decir por qué se usan | Cada prueba debe estar justificada por el riesgo que cubre en el CEM Jehová Rafa |
| Pasos de la auditoría como cronograma | Debe haber una secuencia con semanas, actividades, responsables y entregables |
| Tipos de datos de las pruebas | Debe indicarse qué datos se introducen: tipo, valor válido, inválido y de frontera |

---

## 2. Cómo se llegó a la conclusión

El análisis se hizo en cuatro pasos.

### Paso 1. Lectura del documento contra la exigencia, sección por sección

Se contrastó cada sección de la versión anterior con las cuatro exigencias y se clasificó en tres grupos: **ya cumple**, **cumple a medias** y **no cumple**.

| Sección anterior | Estado frente a la exigencia | Motivo |
|---|---|---|
| 1.1 Identificación | Cumple | Es información del encargo |
| 1.2 Fundamentación | No cumple | Cita a Myers, ISTQB, Bach, Amland, Felderer, ISO 29119-2, ISO 19011, ITAF, IEC, ISO, Sittig y Singh, Coiera, Kushniruk y Patel: es marco teórico |
| 1.3 Objetivos | Cumple | Son verificables |
| 1.4 Alcance | Cumple a medias | Duplica la tipología de pruebas que ya aparece en 1.11 y mezcla «Estado: Ejecutada» con planificación |
| 1.5 Criterios de entrada y salida | Cumple a medias | Enumera condiciones, pero sin responsable ni evidencia |
| 1.6 Riesgos | Cumple a medias | No valora probabilidad ni impacto, así que no permite priorizar |
| 1.7 Módulos y orden | Cumple | Es operativo |
| 1.8 Ambientes | Cumple | Describe entornos reales con versiones |
| 1.9 Equipo | Cumple a medias | Asigna tareas, pero no dice qué entrega cada quien |
| 1.10 Cronograma | No cumple | Siete fases conceptuales sin semanas, sin actividades verificables, sin entregables |
| 1.11 Definición de pruebas | No cumple | Define *qué es* cada prueba en genérico; no dice por qué se usa aquí, ni dónde, ni con qué herramienta |
| 1.12 Tipos de datos | No cumple | Describe los encabezados de una planilla, no tipos de datos |

### Paso 2. Identificación de incoherencias internas

Al cruzar las secciones aparecieron contradicciones que un auditor debe corregir antes de entregar:

1. **El nombre del integrante** aparecía como «Eduard» en 1.1 y «Edouard» en 1.9.
2. **Pruebas del alcance sin definición**: 1.4 listaba 11 pruebas, pero 1.11 solo justificaba 6. Spike, huracán, paralelo, servidor, móvil y aceptación quedaban nombradas y nunca explicadas.
3. **Fase 4 del cronograma incompleta**: mencionaba unitarias, funcionales, integración, portabilidad y seguridad, pero omitía rendimiento y móvil, que sí estaban en el alcance.
4. **Tiempos verbales mezclados**: «se verificó» y «Ejecutada» convivían con un documento que se presenta como planificación.
5. **Alcance móvil ambiguo**: el objetivo hablaba de «aplicación móvil» en general, mientras el alcance dejaba iOS pendiente.
6. **Criterios de entrada sin dueño**: nadie respondía por el respaldo, las cuentas o la autorización del ambiente.

### Paso 3. Definición del criterio de reescritura

Se fijaron cinco criterios para decidir qué se conserva y qué se reescribe:

1. **Práctica sobre teoría.** Lo teórico solo se conserva si sostiene una decisión del encargo.
2. **Justificación por riesgo del negocio.** Cada prueba se explica por el daño que evita en la clínica, no por su definición de manual.
3. **Cronograma verificable.** Cada paso debe tener actividades, responsables y un entregable concreto.
4. **Tipología completa y sin duplicados.** Las pruebas se nombran una sola vez, en 1.11, con su justificación.
5. **Datos de prueba explícitos.** Tipos, valores válidos, inválidos y de frontera, con lotes preparados de antemano.

### Paso 4. Decisiones acordadas con el equipo

| Decisión | Justificación |
|---|---|
| Cronograma desde la **semana 5** | No hay fechas oficiales del trayecto; la semana 5 se declara como primera semana de ejecución y se aclara que es relativa |
| Organización por **semanas, pasos y sesiones** | Permite ubicar el avance sin depender de un calendario oficial |
| **Sin columna «Estado»** | Se acordó dejar el documento como plan limpio, en futuro, para que no mezcle lo planificado con lo ejecutado |
| **Sin sección de severidad de defectos** | Se limita el alcance a lo que pidió la tutora |
| **MIDI al final, en 1.13** | La tutora entregará la información del componente inteligente más adelante; se deja previsto sin afectar las semanas 5 a 12 |
| **Android dentro, iOS fuera** | Coincide con lo que realmente se puede probar; se declara como exclusión explícita |
| **«Edouard»** | Es la grafía correcta y se unifica en todo el documento |

---

## 3. Cambios aplicados

### 3.1 Secciones reescritas

| Sección | Antes | Ahora |
|---|---|---|
| **1.2** | Doce citas bibliográficas | Un párrafo de criterio + tabla de priorización por riesgo con los siete módulos críticos, su riesgo y la prueba aplicada |
| **1.4** | Tabla de pruebas con columna «Estado» | Tabla de elementos auditados con las pruebas aplicadas a cada uno; la tipología vive en 1.11; se declara fuera de alcance MIDI e iOS |
| **1.5** | Lista de condiciones de entrada | Tabla condición → responsable → evidencia |
| **1.6** | Riesgo, efecto y tratamiento | Se agregan probabilidad e impacto, y dos riesgos que faltaban: métricas no comparables y exposición de datos reales |
| **1.9** | Integrante y responsabilidad | Se agrega la evidencia que entrega cada integrante |
| **1.10** | Siete fases conceptuales | Ocho pasos, uno por semana (5 a 12), con actividades, módulos, responsable y evidencia |
| **1.11** | Seis definiciones genéricas | Once pruebas, cada una con por qué se usa en el CEM, dónde, con qué herramienta y con qué datos |
| **1.12** | Definiciones de planilla | Tres tablas: tipos de datos con valores válidos, inválidos y de frontera; lotes de prueba; ejemplo de cruce con la planilla |

### 3.2 Secciones conservadas

| Sección | Qué se mantuvo |
|---|---|
| **1.1** | Todos los datos del encargo; se agrega el inicio en semana 5 y la duración |
| **1.3** | Los objetivos; solo se precisó Android y se declaró iOS fuera de alcance |
| **1.7** | La lista de módulos y el orden de ejecución, ahora coherente con el cronograma |
| **1.8** | Los tres ambientes con sus versiones y la nota sobre comparabilidad de métricas |

### 3.3 Secciones nuevas

| Sección | Contenido |
|---|---|
| **1.13** | Componente MIDI: pruebas previstas, marcadas como pendientes de la información de la tutora |

### 3.4 Trazabilidad con la observación de la tutora

| Lo que pidió | Dónde queda resuelto |
|---|---|
| No buscar conceptos teóricos, llevar a la práctica | 1.2 reduce la teoría a un párrafo; todo el documento habla del CEM Jehová Rafa |
| Nombrar las pruebas y por qué se usan | 1.11, tabla de once pruebas con justificación por riesgo |
| Pasos de la auditoría como cronograma | 1.10, semanas 5 a 12 con actividades, responsables y entregables |
| Tipos de datos de las pruebas | 1.12, tablas A, B y C |

---

## 4. Lo que no se cambió

- Los identificadores de caso ya usados por el equipo (`PF-01` a `PF-05`, `INT-01` a `INT-07`, `P01` a `P04`, `SQL-01` a `SQL-16`) se conservaron para no romper la trazabilidad con las planillas y las matrices ya elaboradas.
- Los 19 módulos y sus nombres.
- Las versiones de los ambientes.
- Los 16 casos y 59 payloads de inyección SQL.
- Los cuatro integrantes y la tutora.

---

## 5. Verificación final

Antes de cerrar la revisión se comprobó que:

1. Ninguna prueba del alcance queda sin definición en 1.11.
2. Cada paso del cronograma tiene responsable y evidencia.
3. Cada tipo de dato de 1.12 tiene valor válido, inválido y de frontera.
4. No quedan referencias a «estado de ejecución» que mezclen plan con resultados.
5. El nombre del integrante es el mismo en todo el documento.
6. Las semanas del cronograma coinciden con el orden de ejecución de 1.7.

---

## 6. Pendiente

- Incorporar el componente MIDI (1.13) cuando la tutora entregue la información.
- Programar las sesiones de aceptación y usabilidad, hoy sin participantes.
- Ejecutar el simulacro de restauración de respaldos.
